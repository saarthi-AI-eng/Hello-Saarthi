import React from 'react';

interface LogoIconProps {
    size?: number | string;
    className?: string;
    style?: React.CSSProperties;
}

export const LogoIcon = ({ size = 24, className = '', style = {} }: LogoIconProps) => {
    return (
        <svg
            width={size}
            height={size}
            viewBox="0 0 48 48"
            fill="none"
            xmlns="http://www.w3.org/2000/svg"
            className={className}
            style={style}
        >
            <path
                d="M32 14 C 32 7, 16 7, 16 14 C 16 24, 32 24, 32 34 C 32 41, 16 41, 16 34"
                stroke="currentColor"
                strokeWidth="4.5"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
            <circle cx="32" cy="14" r="4.5" fill="currentColor" />
            <circle cx="16" cy="34" r="4.5" fill="currentColor" />

            <path d="M12 6 L 13.5 9.5 L 17 11 L 13.5 12.5 L 12 16 L 10.5 12.5 L 7 11 L 10.5 9.5 Z" fill="currentColor" opacity="0.9" />
            <path d="M38 34 L 39.5 36.5 L 42 38 L 39.5 39.5 L 38 42 L 36.5 39.5 L 34 38 L 36.5 36.5 Z" fill="currentColor" opacity="0.9" />
            <path d="M39 12 L 40 14 L 42 15 L 40 16 L 39 18 L 38 16 L 36 15 L 38 14 Z" fill="currentColor" opacity="0.6" />
        </svg>
    );
};
