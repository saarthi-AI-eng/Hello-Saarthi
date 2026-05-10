import os
import json
import time
from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_core.documents import Document
from docling.document_converter import DocumentConverter

KB_STATUS_FILE = "kb_status.json"
EMBEDDING_MODEL = "text-embedding-3-large"

def load_pdf_with_docling(file_path: str) -> List[Document]:
    """
    Loads a PDF using Docling, which handles OCR and layout analysis.
    Returns a list of LangChain Documents (one per page or one for whole doc).
    """
    logger.info(f"Converting {file_path} with Docling...")
    try:
        converter = DocumentConverter()
        result = converter.convert(file_path)
        # Export to Markdown for best RAG performance (preserves headers/tables)
        markdown_text = result.document.export_to_markdown()
        
        # Create a single document for now (or split by headers if we want more granularity later)
        # We'll let the RecursiveCharacterTextSplitter handle the splitting.
        # Metadata is minimal for now.
        return [Document(page_content=markdown_text, metadata={"source": os.path.basename(file_path)})]
    except Exception as e:
        logger.error(f"Docling failed for {file_path}: {e}")
        return []

def get_kb_path(expert_name: str) -> Path:
    """Returns the path to the expert's knowledge base."""
    return Path("knowledge_base") / expert_name

def get_index_path(expert_name: str) -> Path:
    """Returns the path to the local vector store index."""
    return get_kb_path(expert_name) / "vector_store"

def get_retriever(expert_name: str) -> Optional[VectorStoreRetriever]:
    """
    Loads the FAISS index and returns a retriever.
    Returns None if index doesn't exist.
    """
    index_path = get_index_path(expert_name)
    if not index_path.exists():
        return None
        
    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    try:
        vector_store = FAISS.load_local(
            str(index_path), 
            embeddings,
            allow_dangerous_deserialization=True # Safe since we created it
        )
        return vector_store.as_retriever(search_kwargs={"k": 5})
    except Exception as e:
        logger.error(f"Error loading vector store for {expert_name}: {e}")
        return None

def ingest_documents(expert_name: str) -> bool:
    """
    Ingests all PDFs in the expert's KB folder and creates/updates the vector index.
    """
    kb_path = get_kb_path(expert_name)
    if not kb_path.exists():
        logger.warning(f"KB directory {kb_path} not found.")
        return False
        
    # 1. Load Documents
    documents = []
    logger.info(f"Scanning {kb_path} for files...")
    
    # Load PDFs via Docling
    for file_path in kb_path.glob("*.pdf"):
        try:
            docs = load_pdf_with_docling(str(file_path))
            if not docs or not docs[0].page_content.strip():
                 logger.warning(f"WARNING: Docling extracted no text for {file_path.name}.")
            else:
                 logger.info(f"Docling extracted {len(docs[0].page_content)} characters from {file_path.name}")
            documents.extend(docs)
        except Exception as e:
            logger.error(f"Failed to load {file_path.name}: {e}")
    
    # Load TXT files directly (for video transcripts etc.)
    for file_path in kb_path.glob("*.txt"):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read().strip()
            if text:
                documents.append(Document(page_content=text, metadata={"source": file_path.name}))
                logger.info(f"Loaded {len(text)} characters from {file_path.name}")
        except Exception as e:
            logger.error(f"Failed to load {file_path.name}: {e}")
            
    if not documents:
        logger.warning(f"No documents found for {expert_name}.")
        return False
        
    # 2. Split Text
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )
    splits = text_splitter.split_documents(documents)
    logger.info(f"Created {len(splits)} chunks for {expert_name}.")
    
    # 3. Vectorize and Index
    logger.info(f"Embedding and indexing {expert_name}...")
    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL)
    vector_store = FAISS.from_documents(documents=splits, embedding=embeddings)
    
    # 4. Save Index
    index_path = get_index_path(expert_name)
    vector_store.save_local(str(index_path))
    logger.info(f"Index saved to {index_path}")
    return True

def check_and_update_kb_index(expert_name: str) -> bool:
    """
    Checks modification times and re-indexes if necessary.
    """
    kb_path = get_kb_path(expert_name)
    if not kb_path.exists():
        return False
        
    # Check latest file modification
    last_modified = 0.0
    has_files = False
    for ext in ["*.pdf", "*.txt"]:
        for file in kb_path.glob(ext):
            has_files = True
            mtime = file.stat().st_mtime
            if mtime > last_modified:
                last_modified = mtime
            
    if not has_files:
        return False

    # Load status
    status = {}
    if os.path.exists(KB_STATUS_FILE):
        with open(KB_STATUS_FILE, "r") as f:
            try:
                status = json.load(f)
            except json.JSONDecodeError:
                pass
                
    prev_modified = status.get(expert_name, 0.0)
    
    # If newer files exist OR index doesn't exist
    index_missing = not get_index_path(expert_name).exists()
    
    if last_modified > prev_modified or index_missing:
        logger.info(f"Updating Knowledge Base for {expert_name}...")
        success = ingest_documents(expert_name)
        if success:
            status[expert_name] = last_modified
            with open(KB_STATUS_FILE, "w") as f:
                json.dump(status, f)
            return True
            
    return False

def get_expert_description(expert_name: str) -> str:
    """
    Returns the description of the expert. 
    """
    if "expert_1" in expert_name or "notes_agent" in expert_name:
        return "Notes Agent: Specialized in retrieving information from personal notes and documents. Use this when the user asks about meetings, specific personal details, or content from their uploaded notes."
    if "expert_2" in expert_name or "books_agent" in expert_name:
        return "Books Agent: Specialized in answering questions based on the books in the knowledge base. Use this for general knowledge, stories, or content likely found in books."
    if "calculator_agent" in expert_name:
        return "Calculator Agent: Specialized in performing mathematical calculations."
    if "saarthi_agent" in expert_name:
        return "Saarthi Agent: A general, friendly conversational assistant. Use this for greetings, small talk, questions about the user's identity (e.g., 'What is my name?'), referring to previous parts of this conversation, or queries that don't fit the specific Notes, Books, Calculator, or Video experts."
    if "video_agent" in expert_name:
        return "Video Agent: Specialized in answering questions from video lecture transcripts on signals and systems. Use this when the user asks about lecture content, concepts explained in video lectures, or video-based tutorials."
    if "data_analysis_agent" in expert_name:
        return "Data Analysis Agent: Specialized in analyzing uploaded CSV datasets using pandas and numpy. Use this when the user asks to analyze data, explore a dataset, compute statistics, filter rows, find correlations, or any data-related query. Also use this when the user mentions 'data', 'CSV', 'dataset', 'analyze', 'plot', 'statistics', 'columns', or 'rows'."
    return "General Assistant"
