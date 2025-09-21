"use client"

"use client"

import type React from "react"

import { useState } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Send, Loader2, Sparkles, Database, BarChart, Zap } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { generateQuery, type AIQueryResponse } from "@/lib/api"

interface AiPromptInterfaceProps {
  onQueryGenerated?: (query: string) => void
  onQueryExecuted?: (result: AIQueryResponse) => void
  onNewQuery?: (prompt: string) => void
  isLoading?: boolean
  placeholder?: string
}

export function AiPromptInterface({ 
  onQueryGenerated, 
  onQueryExecuted, 
  onNewQuery, 
  isLoading: externalLoading = false,
  placeholder = "Describe what you want to query..."
}: AiPromptInterfaceProps) {
  const [prompt, setPrompt] = useState("")
  const [isGenerating, setIsGenerating] = useState(false)
  const [generatedQuery, setGeneratedQuery] = useState("")
  const [error, setError] = useState<string | null>(null)

  const handleGenerate = async () => {
    if (!prompt.trim()) return

    setIsGenerating(true)
    setError(null)

    // Notify parent about new query
    onNewQuery?.(prompt.trim())

    try {
      // Call the actual AI API
      const result = await generateQuery({
        prompt: prompt.trim(),
        session_id: `session_${Date.now()}`,
        max_retries: 2,
        use_workflow: false, // force direct path for now
        reset_database: true, // Reset database to avoid conflicts
      })

      if (result.success && result.sql) {
        setGeneratedQuery(result.sql)
        onQueryGenerated?.(result.sql)
        // Note: Not calling onQueryExecuted to prevent auto-execution
        // Let user review the code and execute manually
      } else {
        setError(result.error || "Failed to generate query")
      }
    } catch (error) {
      console.error("Error generating query:", error)
      setError(error instanceof Error ? error.message : "Failed to connect to backend")
    } finally {
      setIsGenerating(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault()
      handleGenerate()
    }
  }

  return (
    <div className="space-y-2 lg:space-y-3">
      {/* AI Prompt Header */}
      <div className="flex items-center space-x-2">
        <div className="flex items-center justify-center w-6 h-6 lg:w-8 lg:h-8 bg-primary/10 rounded-full">
          <Sparkles className="h-3 w-3 lg:h-4 lg:w-4 text-primary" />
        </div>
        <h3 className="text-sm lg:text-lg font-semibold text-foreground">AI SQL Generator</h3>
      </div>

      {/* Chat-like Input */}
      <Card className="bg-card/60 backdrop-blur-sm border-border shadow-sm">
        <CardContent className="p-2 lg:p-3">
          <div className="space-y-2 lg:space-y-3">
            <Textarea
              placeholder={placeholder}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={handleKeyDown}
              className="min-h-[60px] lg:min-h-[80px] resize-none bg-background/50 border-border focus:ring-primary/20 text-sm lg:text-base"
              disabled={isGenerating || externalLoading}
            />

            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <div className="text-xs text-muted-foreground order-2 sm:order-1">Press Cmd+Enter to generate</div>
              <Button
                onClick={handleGenerate}
                disabled={!prompt.trim() || isGenerating || externalLoading}
                className="bg-primary hover:bg-primary/90 text-primary-foreground text-sm lg:text-base order-1 sm:order-2"
                size="sm"
              >
                {(isGenerating || externalLoading) ? (
                  <>
                    <Loader2 className="h-3 w-3 lg:h-4 lg:w-4 mr-1 lg:mr-2 animate-spin" />
                    <span>Generating...</span>
                  </>
                ) : (
                  <>
                    <Send className="h-3 w-3 lg:h-4 lg:w-4 mr-1 lg:mr-2" />
                    <span>Generate SQL</span>
                  </>
                )}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Loading Animation */}
      <AnimatePresence>
        {isGenerating && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="flex items-center justify-center space-x-2 py-4"
          >
            <div className="flex space-x-1">
              {[0, 1, 2].map((i) => (
                <motion.div
                  key={i}
                  animate={{
                    scale: [1, 1.2, 1],
                    opacity: [0.5, 1, 0.5],
                  }}
                  transition={{
                    duration: 1,
                    repeat: Number.POSITIVE_INFINITY,
                    delay: i * 0.2,
                  }}
                  className="w-2 h-2 bg-primary rounded-full"
                />
              ))}
            </div>
            <span className="text-sm text-muted-foreground">AI is thinking...</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Error Display */}
      <AnimatePresence>
        {error && !isGenerating && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            <Alert variant="destructive">
              <AlertDescription>
                {error}
              </AlertDescription>
            </Alert>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
