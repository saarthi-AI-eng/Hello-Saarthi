import { ChevronLeft, ChevronRight } from 'lucide-react';
import './Pagination.css';

interface PaginationProps {
  total: number;
  limit: number;
  offset: number;
  onPageChange: (newOffset: number) => void;
  className?: string;
}

export default function Pagination({ total, limit, offset, onPageChange, className = '' }: PaginationProps) {
  const totalPages = limit > 0 ? Math.max(1, Math.ceil(total / limit)) : 1;
  const currentPage = limit > 0 ? Math.min(totalPages, Math.floor(offset / limit) + 1) : 1;
  const hasPrev = offset > 0;
  const hasNext = offset + limit < total;

  return (
    <div className={`pagination ${className}`}>
      <span className="pagination-info">
        Page {currentPage} of {totalPages}
        {total > 0 && (
          <span className="pagination-total"> ({total} total)</span>
        )}
      </span>
      <div className="pagination-buttons">
        <button
          type="button"
          className="btn btn-outline btn-sm"
          disabled={!hasPrev}
          onClick={() => onPageChange(Math.max(0, offset - limit))}
          aria-label="Previous page"
        >
          <ChevronLeft size={16} /> Prev
        </button>
        <button
          type="button"
          className="btn btn-outline btn-sm"
          disabled={!hasNext}
          onClick={() => onPageChange(offset + limit)}
          aria-label="Next page"
        >
          Next <ChevronRight size={16} />
        </button>
      </div>
    </div>
  );
}
