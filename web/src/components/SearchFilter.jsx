import React, { useState, useCallback, useMemo } from 'react';
import { Search, X, Filter, ChevronDown } from 'lucide-react';
import { cn } from './ui';

/**
 * SearchInput - Search input with clear button
 * 
 * @param {Object} props
 * @param {string} props.value - Current search value
 * @param {function} props.onChange - Change handler
 * @param {string} [props.placeholder='搜索...'] - Placeholder text
 * @param {string} [props.className] - Additional CSS classes
 */
export function SearchInput({
    value,
    onChange,
    placeholder = '搜索...',
    className,
}) {
    return (
        <div className={cn('relative', className)}>
            <Search
                className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground pointer-events-none"
                aria-hidden="true"
            />
            <input
                type="text"
                value={value}
                onChange={(e) => onChange(e.target.value)}
                placeholder={placeholder}
                className={cn(
                    'w-full pl-9 pr-8 py-2 text-sm rounded-lg',
                    'bg-muted/50 border border-border/60',
                    'placeholder:text-muted-foreground/60',
                    'focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary/50',
                    'transition-colors'
                )}
                aria-label="Search"
            />
            {value && (
                <button
                    onClick={() => onChange('')}
                    className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded-full hover:bg-muted transition-colors"
                    aria-label="Clear search"
                >
                    <X className="h-3 w-3 text-muted-foreground" />
                </button>
            )}
        </div>
    );
}

/**
 * StatusFilter - Status filter dropdown/chips
 * 
 * @param {Object} props
 * @param {string|null} props.value - Current filter value (null = all)
 * @param {function} props.onChange - Change handler
 * @param {Array<{value: string, label: string}>} props.options - Filter options
 * @param {string} [props.allLabel='全部'] - Label for "all" option
 * @param {'dropdown' | 'chips'} [props.variant='chips'] - Display variant
 * @param {string} [props.className] - Additional CSS classes
 */
export function StatusFilter({
    value,
    onChange,
    options,
    allLabel = '全部',
    variant = 'chips',
    className,
}) {
    const [isOpen, setIsOpen] = useState(false);

    if (variant === 'chips') {
        return (
            <div className={cn('flex flex-wrap gap-1.5', className)} role="radiogroup" aria-label="Filter by status">
                <FilterChip
                    selected={value === null}
                    onClick={() => onChange(null)}
                    aria-checked={value === null}
                >
                    {allLabel}
                </FilterChip>
                {options.map((opt) => (
                    <FilterChip
                        key={opt.value}
                        selected={value === opt.value}
                        onClick={() => onChange(opt.value)}
                        aria-checked={value === opt.value}
                    >
                        {opt.label}
                    </FilterChip>
                ))}
            </div>
        );
    }

    // Dropdown variant
    const selectedLabel = value === null ? allLabel : options.find(o => o.value === value)?.label || allLabel;

    return (
        <div className={cn('relative', className)}>
            <button
                onClick={() => setIsOpen(!isOpen)}
                className={cn(
                    'flex items-center gap-2 px-3 py-2 text-sm rounded-lg',
                    'bg-muted/50 border border-border/60',
                    'hover:bg-muted transition-colors',
                    'focus:outline-none focus:ring-2 focus:ring-primary/50'
                )}
                aria-haspopup="listbox"
                aria-expanded={isOpen}
            >
                <Filter className="h-4 w-4 text-muted-foreground" />
                <span>{selectedLabel}</span>
                <ChevronDown className={cn('h-4 w-4 text-muted-foreground transition-transform', isOpen && 'rotate-180')} />
            </button>

            {isOpen && (
                <>
                    <div
                        className="fixed inset-0 z-40"
                        onClick={() => setIsOpen(false)}
                        aria-hidden="true"
                    />
                    <div
                        className={cn(
                            'absolute top-full left-0 mt-1 z-50 min-w-[120px]',
                            'bg-popover border border-border rounded-lg shadow-lg overflow-hidden'
                        )}
                        role="listbox"
                    >
                        <button
                            onClick={() => { onChange(null); setIsOpen(false); }}
                            className={cn(
                                'w-full px-3 py-2 text-sm text-left',
                                'hover:bg-muted transition-colors',
                                value === null && 'bg-primary/10 text-primary'
                            )}
                            role="option"
                            aria-selected={value === null}
                        >
                            {allLabel}
                        </button>
                        {options.map((opt) => (
                            <button
                                key={opt.value}
                                onClick={() => { onChange(opt.value); setIsOpen(false); }}
                                className={cn(
                                    'w-full px-3 py-2 text-sm text-left',
                                    'hover:bg-muted transition-colors',
                                    value === opt.value && 'bg-primary/10 text-primary'
                                )}
                                role="option"
                                aria-selected={value === opt.value}
                            >
                                {opt.label}
                            </button>
                        ))}
                    </div>
                </>
            )}
        </div>
    );
}

/**
 * FilterChip - Individual filter chip button
 */
function FilterChip({ children, selected, onClick, ...props }) {
    return (
        <button
            onClick={onClick}
            className={cn(
                'px-2.5 py-1 text-xs rounded-full transition-colors',
                'border focus:outline-none focus:ring-2 focus:ring-primary/50',
                selected
                    ? 'bg-primary text-primary-foreground border-primary'
                    : 'bg-muted/50 text-muted-foreground border-border/60 hover:bg-muted hover:text-foreground'
            )}
            role="radio"
            {...props}
        >
            {children}
        </button>
    );
}

/**
 * SearchAndFilter - Combined search and filter component
 * 
 * @param {Object} props
 * @param {string} props.searchValue - Current search value
 * @param {function} props.onSearchChange - Search change handler
 * @param {string|null} props.filterValue - Current filter value
 * @param {function} props.onFilterChange - Filter change handler
 * @param {Array<{value: string, label: string}>} props.filterOptions - Filter options
 * @param {string} [props.searchPlaceholder] - Search placeholder
 * @param {string} [props.allLabel] - All filter label
 * @param {string} [props.className] - Additional CSS classes
 */
export function SearchAndFilter({
    searchValue,
    onSearchChange,
    filterValue,
    onFilterChange,
    filterOptions,
    searchPlaceholder = '搜索...',
    allLabel = '全部',
    className,
}) {
    return (
        <div className={cn('flex flex-col sm:flex-row gap-3', className)}>
            <SearchInput
                value={searchValue}
                onChange={onSearchChange}
                placeholder={searchPlaceholder}
                className="flex-1 sm:max-w-xs"
            />
            <StatusFilter
                value={filterValue}
                onChange={onFilterChange}
                options={filterOptions}
                allLabel={allLabel}
                variant="chips"
            />
        </div>
    );
}

/**
 * Custom hook for search and filter state management
 * 
 * @param {Array} items - Items to filter
 * @param {Object} options - Configuration options
 * @returns {Object} - Filtered items and state handlers
 */
export function useSearchFilter(items, {
    searchFields = ['id', 'url', 'code'],
    statusField = 'status',
    initialStatusFilter = null,
} = {}) {
    const [searchQuery, setSearchQuery] = useState('');
    const [statusFilter, setStatusFilter] = useState(initialStatusFilter);

    const filteredItems = useMemo(() => {
        if (!Array.isArray(items)) return [];

        return items.filter((item) => {
            // Status filter
            if (statusFilter !== null && item[statusField] !== statusFilter) {
                return false;
            }

            // Search filter
            if (searchQuery.trim()) {
                const query = searchQuery.toLowerCase().trim();
                return searchFields.some((field) => {
                    const value = item[field];
                    if (value === null || value === undefined) return false;
                    return String(value).toLowerCase().includes(query);
                });
            }

            return true;
        });
    }, [items, searchQuery, statusFilter, searchFields, statusField]);

    const clearFilters = useCallback(() => {
        setSearchQuery('');
        setStatusFilter(null);
    }, []);

    const hasActiveFilters = searchQuery.trim() !== '' || statusFilter !== null;

    return {
        searchQuery,
        setSearchQuery,
        statusFilter,
        setStatusFilter,
        filteredItems,
        clearFilters,
        hasActiveFilters,
    };
}

export default SearchAndFilter;
