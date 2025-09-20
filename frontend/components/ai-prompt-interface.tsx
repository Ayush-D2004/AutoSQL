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
        onQueryExecuted?.(result)
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
    <div className="space-y-3">
      {/* AI Prompt Header */}
      <div className="flex items-center space-x-2">
        <div className="flex items-center justify-center w-8 h-8 bg-primary/10 rounded-full">
          <Sparkles className="h-4 w-4 text-primary" />
        </div>
        <h3 className="text-lg font-semibold text-foreground">AI SQL Generator</h3>
      </div>

      {/* Chat-like Input */}
      <Card className="bg-card/60 backdrop-blur-sm border-border shadow-sm">
        <CardContent className="p-3">
          <div className="space-y-3">
            <Textarea
              placeholder={placeholder}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              onKeyDown={handleKeyDown}
              className="min-h-[80px] resize-none bg-background/50 border-border focus:ring-primary/20"
              disabled={isGenerating || externalLoading}
            />

            <div className="flex items-center justify-between">
              <div className="text-xs text-muted-foreground">Press Cmd+Enter to generate</div>
              <Button
                onClick={handleGenerate}
                disabled={!prompt.trim() || isGenerating || externalLoading}
                className="bg-primary hover:bg-primary/90 text-primary-foreground"
              >
                {(isGenerating || externalLoading) ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Generating...
                  </>
                ) : (
                  <>
                    <Send className="h-4 w-4 mr-2" />
                    Generate SQL
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
