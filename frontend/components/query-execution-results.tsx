"use client"

import React, { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import {
  Play,
  Download,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  Clock,
  ChevronLeft,
  ChevronRight,
  ArrowUpDown,
  ArrowUp,
  ArrowDown,
  ExternalLink,
  GripVertical,
  Maximize2,
  Table as TableIcon,
  X,
} from "lucide-react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import type { AIQueryResponse, TableResult } from "@/lib/api"

interface QueryResult {
  columns: string[]
  rows: any[][]
  totalRows: number
  executionTime: number
  affectedRows: number
  table_results?: TableResult[]
  metadata?: {
    total_statements?: number
    statement_types?: string[]
    all_successful?: boolean
    query_type?: string
    [key: string]: any
  }
}

interface QueryError {
  message: string
  line?: number
  column?: number
}

interface QueryExecutionResultsProps {
  query?: string
  results?: AIQueryResponse | null
  onExecute?: (query: string) => void
  onOpenTableInNewTab?: (tableResult: TableResult) => void
}

interface TableDisplayProps {
  tableResult: TableResult
  index: number
  onOpenInNewTab?: (tableResult: TableResult) => void
  onMaximize?: (tableResult: TableResult) => void
  showDragHandle?: boolean
  isMaximized?: boolean
}

// Removed hardcoded mock data - now using real query results from backend

const TableDisplay: React.FC<TableDisplayProps> = ({ 
  tableResult, 
  index, 
  onOpenInNewTab,
  onMaximize,
  showDragHandle = true,
  isMaximized = false
}) => {
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)
  const [sortColumn, setSortColumn] = useState<string | null>(null)
  const [sortDirection, setSortDirection] = useState<"asc" | "desc" | null>(null)

  const totalPages = Math.ceil(tableResult.rows.length / pageSize)
  const startRow = (currentPage - 1) * pageSize + 1
  const endRow = Math.min(currentPage * pageSize, tableResult.rows.length)
  const totalRows = tableResult.row_count || tableResult.rows.length

  const handleSort = (column: string) => {
    if (sortColumn === column) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : prev === "desc" ? null : "asc"))
      if (sortDirection === "desc") {
        setSortColumn(null)
      }
    } else {
      setSortColumn(column)
      setSortDirection("asc")
    }
  }

  const getSortIcon = (column: string) => {
    if (sortColumn !== column) return <ArrowUpDown className="h-3 w-3" />
    if (sortDirection === "asc") return <ArrowUp className="h-3 w-3" />
    if (sortDirection === "desc") return <ArrowDown className="h-3 w-3" />
    return <ArrowUpDown className="h-3 w-3" />
  }

  // Sort data if needed
  const sortedRows = React.useMemo(() => {
    if (!sortColumn || !sortDirection) return tableResult.rows

    return [...tableResult.rows].sort((a, b) => {
      const aVal = a[sortColumn]
      const bVal = b[sortColumn]
      
      if (aVal === null || aVal === undefined) return 1
      if (bVal === null || bVal === undefined) return -1
      
      if (aVal < bVal) return sortDirection === "asc" ? -1 : 1
      if (aVal > bVal) return sortDirection === "asc" ? 1 : -1
      return 0
    })
  }, [tableResult.rows, sortColumn, sortDirection])

  // Paginate data
  const paginatedRows = sortedRows.slice((currentPage - 1) * pageSize, currentPage * pageSize)

  return (
    <Card className="bg-card/60 backdrop-blur-sm border-border shadow-sm">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            {showDragHandle && (
              <div className="cursor-grab active:cursor-grabbing">
                <GripVertical className="h-4 w-4 text-muted-foreground" />
              </div>
            )}
            <div className="flex items-center space-x-2">
              <TableIcon className="h-4 w-4 text-primary" />
              <h3 className="text-sm font-medium">{tableResult.table_name || `Table ${index + 1}`}</h3>
            </div>
            <div className="text-sm text-muted-foreground">
              Showing {startRow}-{endRow} of {totalRows.toLocaleString()} rows
            </div>
            <Badge variant="secondary" className="text-xs">
              {tableResult.execution_time_ms.toFixed(1)}ms
            </Badge>
          </div>
          <div className="flex items-center space-x-2">
            {onOpenInNewTab && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onOpenInNewTab(tableResult)}
                className="h-8 w-8 p-0"
              >
                <ExternalLink className="h-3 w-3" />
              </Button>
            )}
            {onMaximize && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => onMaximize(tableResult)}
                className="h-8 w-8 p-0"
                title={isMaximized ? "Minimize" : "Maximize"}
              >
                <Maximize2 className="h-3 w-3" />
              </Button>
            )}
          </div>
        </div>
        
        {/* Pagination and page size controls */}
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center space-x-2">
            <span className="text-muted-foreground">Rows per page:</span>
            <Select value={pageSize.toString()} onValueChange={(value) => {
              setPageSize(parseInt(value))
              setCurrentPage(1)
            }}>
              <SelectTrigger className="w-16 h-7">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="10">10</SelectItem>
                <SelectItem value="25">25</SelectItem>
                <SelectItem value="50">50</SelectItem>
                <SelectItem value="100">100</SelectItem>
              </SelectContent>
            </Select>
          </div>
          
          {totalPages > 1 && (
            <div className="flex items-center space-x-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage <= 1}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-muted-foreground">
                Page {currentPage} of {totalPages}
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                disabled={currentPage >= totalPages}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          )}
        </div>
      </CardHeader>
      
      <CardContent className="p-0">
        <div className={`border rounded-md ${isMaximized ? 'max-h-[80vh]' : 'max-h-96'} overflow-hidden`}>
          <div className="overflow-auto h-full scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100">
            <Table>
              <TableHeader className="sticky top-0 bg-background/95 backdrop-blur-sm z-10">
                <TableRow>
                  {tableResult.columns.map((column) => (
                    <TableHead
                      key={column}
                      className="cursor-pointer hover:bg-muted/50 select-none min-w-[120px] whitespace-nowrap"
                      onClick={() => handleSort(column)}
                    >
                      <div className="flex items-center justify-between">
                        <span className="truncate">{column}</span>
                        {getSortIcon(column)}
                      </div>
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {paginatedRows.map((row, rowIndex) => (
                  <TableRow key={rowIndex} className="hover:bg-muted/30">
                    {tableResult.columns.map((column) => (
                      <TableCell key={column} className="font-mono text-xs min-w-[120px]">
                        <div className="max-w-xs truncate" title={String(row[column] ?? "")}>
                          {row[column] === null ? (
                            <span className="text-muted-foreground italic">NULL</span>
                          ) : (
                            String(row[column])
                          )}
                        </div>
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

type SortDirection = "asc" | "desc" | null

export function QueryExecutionResults({ query, results: aiResults, onExecute, onOpenTableInNewTab }: QueryExecutionResultsProps) {
  const [isExecuting, setIsExecuting] = useState(false)
  const [results, setResults] = useState<QueryResult | null>(null)
  const [error, setError] = useState<QueryError | null>(null)
  const [maximizedTable, setMaximizedTable] = useState<TableResult | null>(null)

  // Function to maximize/minimize a table
  const handleMaximize = (tableResult: TableResult) => {
    setMaximizedTable(maximizedTable ? null : tableResult)
  }

  // Update results when AI results are passed
  useEffect(() => {
    if (aiResults && aiResults.success) {
      // Convert AI results to our QueryResult format
      const formattedResults: QueryResult = {
        columns: aiResults.columns || [],
        rows: (aiResults.rows || []).map(row => 
          aiResults.columns?.map(col => row[col]) || []
        ),
        totalRows: aiResults.row_count || 0,
        executionTime: aiResults.execution_time_ms || 0,
        affectedRows: aiResults.affected_rows || 0,
        // Include table_results if available (new format)
        table_results: aiResults.table_results || []
      }
      setResults(formattedResults)
      setError(null)
    } else if (aiResults && !aiResults.success) {
      setError({
        message: aiResults.error || "Query execution failed"
      })
      setResults(null)
    }
  }, [aiResults])

  // Helper function to determine if query returns data rows
  const isDataQuery = (sql: string): boolean => {
    const trimmed = sql.trim().toUpperCase()
    return trimmed.startsWith('SELECT') || trimmed.startsWith('WITH')
  }

  // Helper function to get query type for display
  const getQueryType = (sql: string): string => {
    const trimmed = sql.trim().toUpperCase()
    if (trimmed.startsWith('CREATE')) return 'CREATE'
    if (trimmed.startsWith('INSERT')) return 'INSERT'
    if (trimmed.startsWith('UPDATE')) return 'UPDATE'
    if (trimmed.startsWith('DELETE')) return 'DELETE'
    if (trimmed.startsWith('ALTER')) return 'ALTER'
    if (trimmed.startsWith('DROP')) return 'DROP'
    if (trimmed.startsWith('SELECT')) return 'SELECT'
    return 'QUERY'
  }

  const handleExecute = async () => {
    if (!query?.trim()) return

    setIsExecuting(true)
    setError(null)
    setResults(null)

    try {
      // Call the actual onExecute function passed from parent
      if (onExecute) {
        await onExecute(query)
      } else {
        // If no onExecute function provided, show message
        throw new Error("No execution handler provided. Please use the execute button in the SQL editor.")
      }
    } catch (err) {
      setError({
        message: err instanceof Error ? err.message : "An unknown error occurred",
        line: 1,
        column: 1,
      })
    } finally {
      setIsExecuting(false)
    }
  }

  const handleExport = () => {
    if (!results) return

    const csv = [results.columns.join(","), ...results.rows.map((row) => row.join(","))].join("\n")

    const blob = new Blob([csv], { type: "text/csv" })
    const url = URL.createObjectURL(blob)
    const a = document.createElement("a")
    a.href = url
    a.download = "query_results.csv"
    a.click()
    URL.revokeObjectURL(url)
  }

  // Remove automatic execution - let parent components handle execution

  return (
    <div className="space-y-4">
      {/* Execution Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <Play className="h-5 w-5 text-primary" />
          <h3 className="text-lg font-semibold text-foreground">Query Results</h3>
        </div>

        <div className="flex items-center space-x-2">
          {results && (
            <Button variant="outline" size="sm" onClick={handleExport}>
              <Download className="h-4 w-4 mr-1" />
              Export CSV
            </Button>
          )}
        </div>
      </div>

      {/* Execution Status */}
      <AnimatePresence mode="wait">
        {isExecuting && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
            <Card className="bg-card/60 backdrop-blur-sm border-border">
              <CardContent className="p-4">
                <div className="flex items-center space-x-3">
                  <div className="animate-spin">
                    <RefreshCw className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">Executing query...</p>
                    <p className="text-xs text-muted-foreground">Please wait while we process your request</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {error && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }}>
            <Alert className="border-destructive/50 bg-destructive/10">
              <AlertCircle className="h-4 w-4 text-destructive" />
              <AlertDescription className="text-destructive">
                <div className="space-y-1">
                  <p className="font-medium">Query execution failed</p>
                  <p className="text-sm">{error.message}</p>
                  {error.line && (
                    <p className="text-xs">
                      Line {error.line}, Column {error.column}
                    </p>
                  )}
                </div>
              </AlertDescription>
            </Alert>
          </motion.div>
        )}

        {results && !isExecuting && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="space-y-4"
          >
            {/* Results Table or Success Message */}
            {/* Check if we have table results from multiple SELECT statements */}
            {results.table_results && results.table_results.length > 0 ? (
              <div className="space-y-4">
                {results.table_results.length === 1 ? (
                  // Single table - display directly without tabs
                  <TableDisplay
                    tableResult={results.table_results[0]}
                    index={0}
                    onOpenInNewTab={onOpenTableInNewTab}
                    onMaximize={handleMaximize}
                    isMaximized={maximizedTable === results.table_results[0]}
                    showDragHandle={false}
                  />
                ) : (
                  // Multiple tables - display in tabs
                  <Tabs defaultValue="table-0" className="space-y-4">
                    <TabsList className="grid w-full bg-muted/30" style={{ gridTemplateColumns: `repeat(${results.table_results.length}, 1fr)` }}>
                      {results.table_results.map((tableResult, index) => (
                        <TabsTrigger 
                          key={index} 
                          value={`table-${index}`}
                          className="flex items-center space-x-2 text-sm"
                        >
                          <TableIcon className="h-3 w-3" />
                          <span>Table {index + 1}</span>
                          <Badge variant="secondary" className="text-xs ml-1">
                            {tableResult.row_count?.toLocaleString() || tableResult.rows.length.toLocaleString()}
                          </Badge>
                        </TabsTrigger>
                      ))}
                    </TabsList>
                    
                    {results.table_results.map((tableResult, index) => (
                      <TabsContent key={index} value={`table-${index}`} className="space-y-4">
                        <TableDisplay
                          tableResult={tableResult}
                          index={index}
                          onOpenInNewTab={onOpenTableInNewTab}
                          onMaximize={handleMaximize}
                          isMaximized={maximizedTable === tableResult}
                          showDragHandle={false}
                        />
                      </TabsContent>
                    ))}
                  </Tabs>
                )}
              </div>
            ) : results.columns && results.columns.length > 0 ? (
              // Fallback for old single table format (backwards compatibility)
              <TableDisplay
                tableResult={{
                  columns: results.columns,
                  rows: results.rows.map((row, index) => {
                    const rowObj: Record<string, any> = {}
                    results.columns.forEach((col, colIndex) => {
                      rowObj[col] = row[colIndex]
                    })
                    return rowObj
                  }),
                  row_count: results.totalRows,
                  affected_rows: results.affectedRows,
                  execution_time_ms: results.executionTime,
                  query: query || '',
                  query_type: 'SELECT'
                }}
                index={0}
                onOpenInNewTab={onOpenTableInNewTab}
                onMaximize={handleMaximize}
                isMaximized={maximizedTable !== null}
              />
            ) : query && !isDataQuery(query) ? (
              // For DDL/DML operations, don't show success message - just remain silent
              null
            ) : null}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Empty State */}
      {!isExecuting && !results && !error && (
        <Card className="bg-card/40 backdrop-blur-sm border-border border-dashed">
          <CardContent className="p-8 text-center">
            <Play className="h-12 w-12 mx-auto mb-4 text-muted-foreground opacity-50" />
            <h4 className="text-lg font-medium text-foreground mb-2">Ready to execute</h4>
            <p className="text-sm text-muted-foreground">
              Write a query in the editor above and click "Execute Query" to see results here.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
