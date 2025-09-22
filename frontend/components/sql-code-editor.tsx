"use client"

import React, { useState, useRef, useEffect } from 'react'
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { Play, Copy, Trash2, FileText, Maximize2, Minimize2 } from "lucide-react"
import { useToast } from "@/hooks/use-toast"

interface SqlCodeEditorProps {
  value: string
  onChange?: (value: string) => void
  onExecute: () => void
  isExecuting?: boolean
  placeholder?: string
  className?: string
}

export function SqlCodeEditor({
  value,
  onChange,
  onExecute,
  isExecuting = false,
  placeholder = "Enter your SQL query here...",
  className = ""
}: SqlCodeEditorProps) {
  const { toast } = useToast()
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [isMaximized, setIsMaximized] = useState(false)

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      // Don't auto-resize, let CSS handle the height
      // This ensures consistent layout using viewport height
    }
  }, [value, isMaximized])

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Ctrl+Enter to execute
    if (e.ctrlKey && e.key === 'Enter') {
      e.preventDefault()
      onExecute()
    }
    
    // Tab for indentation
    if (e.key === 'Tab') {
      e.preventDefault()
      const textarea = e.currentTarget
      const start = textarea.selectionStart
      const end = textarea.selectionEnd
      const newValue = value.substring(0, start) + '  ' + value.substring(end)
      onChange?.(newValue)
      
      // Set cursor position after the inserted spaces
      setTimeout(() => {
        textarea.selectionStart = textarea.selectionEnd = start + 2
      }, 0)
    }
  }

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(value || "")
      toast({
        title: "Copied!",
        description: "SQL query copied to clipboard",
      })
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to copy to clipboard",
        variant: "destructive",
      })
    }
  }

  const clearEditor = () => {
    onChange?.('')
    textareaRef.current?.focus()
  }

  const formatSQL = () => {
    if (!value || !value.trim()) return
    
    // Basic SQL formatting
    const formatted = value
      .replace(/\bSELECT\b/gi, 'SELECT')
      .replace(/\bFROM\b/gi, 'FROM')
      .replace(/\bWHERE\b/gi, 'WHERE')
      .replace(/\bJOIN\b/gi, 'JOIN')
      .replace(/\bINNER JOIN\b/gi, 'INNER JOIN')
      .replace(/\bLEFT JOIN\b/gi, 'LEFT JOIN')
      .replace(/\bRIGHT JOIN\b/gi, 'RIGHT JOIN')
      .replace(/\bORDER BY\b/gi, 'ORDER BY')
      .replace(/\bGROUP BY\b/gi, 'GROUP BY')
      .replace(/\bHAVING\b/gi, 'HAVING')
      .replace(/\bLIMIT\b/gi, 'LIMIT')
      .replace(/\bINSERT\b/gi, 'INSERT')
      .replace(/\bUPDATE\b/gi, 'UPDATE')
      .replace(/\bDELETE\b/gi, 'DELETE')
      .replace(/\bCREATE\b/gi, 'CREATE')
      .replace(/\bDROP\b/gi, 'DROP')
      .replace(/\bALTER\b/gi, 'ALTER')
    
    onChange?.(formatted)
    toast({
      title: "Formatted!",
      description: "SQL query has been formatted",
    })
  }

  return (
    <div className={`${className} ${isMaximized ? 'fixed inset-4 z-50' : ''} h-full flex flex-col`}>
      <Card className="flex-1 flex flex-col">
        <CardHeader className="pb-3 flex-shrink-0">
          <div className="flex items-center justify-between">
            <CardTitle className="text-lg font-semibold">SQL Query Editor</CardTitle>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={copyToClipboard}
                disabled={!value || !value.trim()}
              >
                <Copy className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={formatSQL}
                disabled={!value || !value.trim()}
              >
                <FileText className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={clearEditor}
                disabled={!value || !value.trim()}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setIsMaximized(!isMaximized)}
              >
                {isMaximized ? (
                  <Minimize2 className="h-4 w-4" />
                ) : (
                  <Maximize2 className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4 flex-1 flex flex-col pb-8">
          <div className="relative flex-1">
            <Textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => onChange?.(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholder}
              className="font-mono resize-none w-full h-full focus:ring-2 focus:ring-blue-500 scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100"
              style={{
                minHeight: isMaximized ? 'calc(100vh - 200px)' : '400px',
                height: isMaximized ? 'calc(100vh - 200px)' : 'calc(100vh - 300px)'
              }}
            />
            {value && value.trim() && (
              <div className="absolute bottom-2 right-2 text-xs text-muted-foreground bg-background px-2 py-1 rounded border">
                {value.trim().split('\n').length} lines • {value.length} chars
              </div>
            )}
          </div>
          
          <div className="flex items-center justify-between flex-shrink-0 pt-4">
            <div className="text-sm text-muted-foreground">
              Press <kbd className="px-2 py-1 text-xs font-mono bg-muted rounded">Ctrl + Enter</kbd> to execute
            </div>
            <Button 
              onClick={onExecute}
              disabled={!value || !value.trim() || isExecuting}
              className="min-w-[100px]"
            >
              {isExecuting ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  Running...
                </>
              ) : (
                <>
                  <Play className="h-4 w-4 mr-2" />
                  Execute
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}