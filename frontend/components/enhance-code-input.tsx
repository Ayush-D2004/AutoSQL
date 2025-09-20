"use client"

import React, { useState } from 'react'
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Textarea } from "@/components/ui/textarea"
import { Sparkles, Copy, Trash2 } from "lucide-react"
import { useToast } from "@/hooks/use-toast"
import { enhanceCode } from "@/lib/api"

interface EnhanceCodeInputProps {
  value?: string
  onChange?: (value: string) => void
  onEnhance?: (code: string, type: string) => void
  currentSQL?: string
  onPromptSubmitted?: (prompt: string) => void
  onEnhancedCode?: (sql: string) => void
  isEnhancing?: boolean
  placeholder?: string
  className?: string
}

export function EnhanceCodeInput({
  value,
  onChange,
  onEnhance,
  currentSQL,
  onPromptSubmitted,
  onEnhancedCode,
  isEnhancing = false,
  placeholder = "Enter your code to enhance...",
  className = ""
}: EnhanceCodeInputProps) {
  const { toast } = useToast()
  const [enhanceType, setEnhanceType] = useState("optimize")
  const [localValue, setLocalValue] = useState(value || currentSQL || "")

  // Update local value when currentSQL changes
  React.useEffect(() => {
    if (currentSQL && !value) {
      setLocalValue(currentSQL)
    }
  }, [currentSQL, value])

  const currentValue = value || localValue
  const handleChange = onChange || setLocalValue

  const enhanceOptions = [
    { value: "optimize", label: "Optimize Performance" },
    { value: "readability", label: "Improve Readability" },
    { value: "security", label: "Enhance Security" },
    { value: "best-practices", label: "Apply Best Practices" },
    { value: "documentation", label: "Add Documentation" },
    { value: "error-handling", label: "Add Error Handling" },
    { value: "modernize", label: "Modernize Syntax" },
    { value: "refactor", label: "Refactor Structure" }
  ]

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(currentValue || "")
      toast({
        title: "Copied!",
        description: "Code copied to clipboard",
      })
    } catch (err) {
      toast({
        title: "Error",
        description: "Failed to copy to clipboard",
        variant: "destructive",
      })
    }
  }

  const clearInput = () => {
    handleChange('')
  }

  const handleEnhance = async () => {
    if (!currentValue || !currentValue.trim()) {
      toast({
        title: "No code to enhance",
        description: "Please enter some code first",
        variant: "destructive",
      })
      return
    }
    
    try {
      if (onEnhance) {
        onEnhance(currentValue, enhanceType)
      } else if (onEnhancedCode) {
        // Call the API to enhance the code
        const response = await enhanceCode({
          prompt: `Enhance this code: ${enhanceType}`,
          current_sql: currentValue
        })
        onEnhancedCode(response.sql || currentValue)
      }
    } catch (error) {
      toast({
        title: "Enhancement failed",
        description: "Failed to enhance the code. Please try again.",
        variant: "destructive",
      })
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Ctrl+Enter to enhance
    if (e.ctrlKey && e.key === 'Enter') {
      e.preventDefault()
      handleEnhance()
    }
    
    // Tab for indentation
    if (e.key === 'Tab') {
      e.preventDefault()
      const textarea = e.currentTarget
      const start = textarea.selectionStart
      const end = textarea.selectionEnd
      const newValue = (currentValue || "").substring(0, start) + '  ' + (currentValue || "").substring(end)
      handleChange(newValue)
      
      // Set cursor position after the inserted spaces
      setTimeout(() => {
        textarea.selectionStart = textarea.selectionEnd = start + 2
      }, 0)
    }
  }

  return (
    <Card className={className}>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg font-semibold">Code Enhancement</CardTitle>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={copyToClipboard}
              disabled={!currentValue || !currentValue.trim()}
            >
              <Copy className="h-4 w-4" />
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={clearInput}
              disabled={!currentValue || !currentValue.trim()}
            >
              <Trash2 className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="relative">
          <Textarea
            value={currentValue}
            onChange={(e) => handleChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            className="font-mono resize-none min-h-[120px] focus:ring-2 focus:ring-purple-500"
          />
          {currentValue && currentValue.trim() && (
            <div className="absolute bottom-2 right-2 text-xs text-muted-foreground bg-background px-2 py-1 rounded border">
              {currentValue.trim().split('\n').length} lines • {currentValue.length} chars
            </div>
          )}
        </div>
        
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            Press <kbd className="px-2 py-1 text-xs font-mono bg-muted rounded">Ctrl + Enter</kbd> to enhance
          </div>
          <Button 
            onClick={handleEnhance}
            disabled={!currentValue || !currentValue.trim() || isEnhancing}
            className="min-w-[120px] bg-purple-600 hover:bg-purple-700"
          >
            {isEnhancing ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                Enhancing...
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4 mr-2" />
                Enhance Code
              </>
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}