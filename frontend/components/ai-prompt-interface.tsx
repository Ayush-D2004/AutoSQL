"use client"

"use client"

import type React from "react"

import { useState, useRef, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Send, Loader2, Sparkles, Database, BarChart, Zap, Upload, X, Image as ImageIcon, FileText, File } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { generateQuery, solveFromInput, type AIQueryResponse, type SolveResponse } from "@/lib/api"

interface AiPromptInterfaceProps {
  onQueryGenerated?: (query: string) => void
  onQueryExecuted?: (result: AIQueryResponse) => void
  onSolveResponse?: (result: SolveResponse) => void
  onNewQuery?: (prompt: string) => void
  isLoading?: boolean
  placeholder?: string
}

export function AiPromptInterface({ 
  onQueryGenerated, 
  onQueryExecuted, 
  onSolveResponse,
  onNewQuery, 
  isLoading: externalLoading = false,
  placeholder = "Describe what you want to query..."
}: AiPromptInterfaceProps) {
  const [prompt, setPrompt] = useState("")
  const [isGenerating, setIsGenerating] = useState(false)
  const [generatedQuery, setGeneratedQuery] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [selectedImages, setSelectedImages] = useState<File[]>([])
  const [imagePreviews, setImagePreviews] = useState<string[]>([])
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const fileInputRef = useRef<HTMLInputElement>(null)
  const documentInputRef = useRef<HTMLInputElement>(null)

  // Cleanup image previews on component unmount
  useEffect(() => {
    return () => {
      imagePreviews.forEach(url => URL.revokeObjectURL(url))
    }
  }, [])

  const handleGenerate = async () => {
    if (!prompt.trim() && selectedImages.length === 0 && selectedFiles.length === 0) return

    setIsGenerating(true)
    setError(null)

    // Notify parent about new query
    onNewQuery?.(prompt.trim() || "File-based query")

    try {
      // If images or files are selected, use the solve endpoint
      if (selectedImages.length > 0 || selectedFiles.length > 0) {
        const allFiles = [...selectedImages, ...selectedFiles]
        const result = await solveFromInput(
          prompt.trim() || undefined,
          allFiles
        )

        if (result.success && result.response) {
          // Check if the response contains SQL code
          const sqlMatches = result.response.match(/```sql\n([\s\S]*?)\n```/g)
          if (sqlMatches && sqlMatches.length > 0) {
            // Extract the first SQL query
            const firstSqlMatch = sqlMatches[0].replace(/```sql\n/, '').replace(/\n```/, '')
            setGeneratedQuery(firstSqlMatch)
            onQueryGenerated?.(firstSqlMatch)
          }
          
          // Call solve response handler if provided
          onSolveResponse?.(result)
          
          // Clear input and files after successful response
          setPrompt("")
          clearImages()
          clearFiles()
        } else {
          setError(result.error || "Failed to process images")
        }
      } else {
        // Regular text-only flow
        const result = await generateQuery({
          prompt: prompt.trim(),
          session_id: `session_${Date.now()}`,
          max_retries: 2,
          use_workflow: false,
          reset_database: true,
        })

        if (result.success && result.sql) {
          setGeneratedQuery(result.sql)
          onQueryGenerated?.(result.sql)
          
          // Clear input after successful response
          setPrompt("")
        } else {
          setError(result.error || "Failed to generate query")
        }
      }
    } catch (error) {
      console.error("Error generating response:", error)
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

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    const validFiles = files.filter(file => 
      file.type === 'image/png' || file.type === 'image/jpeg' || file.type === 'image/jpg'
    )

    if (validFiles.length !== files.length) {
      setError("Only PNG and JPEG images are allowed")
      return
    }

    setSelectedImages(validFiles)
    
    // Create previews
    const previews = validFiles.map(file => {
      return URL.createObjectURL(file)
    })
    
    // Clean up old previews
    imagePreviews.forEach(url => URL.revokeObjectURL(url))
    setImagePreviews(previews)
    setError(null)
  }

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || [])
    const allowedTypes = [
      'application/json',
      'text/plain',
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
      'text/csv',
      'application/vnd.ms-excel'
    ]
    
    const validFiles = files.filter(file => {
      const isValidType = allowedTypes.includes(file.type) || 
                         file.name.endsWith('.sql') || 
                         file.name.endsWith('.json') ||
                         file.name.endsWith('.xlsx') ||
                         file.name.endsWith('.csv')
      return isValidType
    })

    if (validFiles.length !== files.length) {
      setError("Only .sql, .json, .xlsx, and .csv files are allowed")
      return
    }

    setSelectedFiles(validFiles)
    setError(null)
  }

  const removeImage = (index: number) => {
    removeFile(index, 'image')
  }

  const clearImages = () => {
    // Clean up all preview URLs
    imagePreviews.forEach(url => URL.revokeObjectURL(url))
    
    setSelectedImages([])
    setImagePreviews([])
  }

  const clearFiles = () => {
    setSelectedFiles([])
  }

  const removeFile = (index: number, type: 'image' | 'file') => {
    if (type === 'image') {
      const newImages = selectedImages.filter((_, i) => i !== index)
      const newPreviews = imagePreviews.filter((_, i) => i !== index)
      
      // Clean up the removed preview URL
      URL.revokeObjectURL(imagePreviews[index])
      
      setSelectedImages(newImages)
      setImagePreviews(newPreviews)
    } else {
      const newFiles = selectedFiles.filter((_, i) => i !== index)
      setSelectedFiles(newFiles)
    }
  }

  const handleUploadClick = () => {
    fileInputRef.current?.click()
  }

  const handleDocumentUploadClick = () => {
    documentInputRef.current?.click()
  }

  const getFileIcon = (fileName: string) => {
    const extension = fileName.split('.').pop()?.toLowerCase()
    switch (extension) {
      case 'sql':
        return <Database className="h-4 w-4" />
      case 'json':
        return <FileText className="h-4 w-4" />
      case 'xlsx':
      case 'csv':
        return <BarChart className="h-4 w-4" />
      default:
        return <File className="h-4 w-4" />
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

            {/* File Upload Section */}
            <div className="space-y-2">
              {/* Image Previews */}
              {selectedImages.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-muted-foreground">Images</h4>
                  <div className="flex flex-wrap gap-2">
                    {imagePreviews.map((preview, index) => (
                      <motion.div
                        key={index}
                        initial={{ opacity: 0, scale: 0.8 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className="relative group"
                      >
                        <div className="w-16 h-16 lg:w-20 lg:h-20 rounded-lg overflow-hidden border-2 border-border bg-background">
                          <img
                            src={preview}
                            alt={`Preview ${index + 1}`}
                            className="w-full h-full object-cover"
                          />
                        </div>
                        <button
                          onClick={() => removeImage(index)}
                          className="absolute -top-1 -right-1 w-5 h-5 bg-destructive text-destructive-foreground rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity text-xs"
                          disabled={isGenerating || externalLoading}
                        >
                          <X className="h-3 w-3" />
                        </button>
                      </motion.div>
                    ))}
                  </div>
                </div>
              )}

              {/* Document Files */}
              {selectedFiles.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-sm font-medium text-muted-foreground">Documents</h4>
                  <div className="space-y-1">
                    {selectedFiles.map((file, index) => (
                      <motion.div
                        key={index}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        className="flex items-center justify-between p-2 bg-background/50 rounded-md border border-border group"
                      >
                        <div className="flex items-center gap-2">
                          {getFileIcon(file.name)}
                          <span className="text-sm text-foreground">{file.name}</span>
                          <span className="text-xs text-muted-foreground">
                            ({(file.size / 1024).toFixed(1)} KB)
                          </span>
                        </div>
                        <button
                          onClick={() => removeFile(index, 'file')}
                          className="w-4 h-4 bg-destructive text-destructive-foreground rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity text-xs"
                          disabled={isGenerating || externalLoading}
                        >
                          <X className="h-2 w-2" />
                        </button>
                      </motion.div>
                    ))}
                  </div>
                </div>
              )}

              {/* Hidden file inputs */}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/png,image/jpeg,image/jpg"
                multiple
                onChange={handleImageUpload}
                className="hidden"
                disabled={isGenerating || externalLoading}
              />
              
              <input
                ref={documentInputRef}
                type="file"
                accept=".sql,.json,.xlsx,.csv,text/plain,application/json,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
                multiple
                onChange={handleFileUpload}
                className="hidden"
                disabled={isGenerating || externalLoading}
              />
            </div>

            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <div className="flex items-center gap-2 order-2 sm:order-1">
                <Button
                  onClick={handleUploadClick}
                  variant="outline"
                  size="sm"
                  disabled={isGenerating || externalLoading}
                  className="flex items-center gap-1"
                >
                  <ImageIcon className="h-3 w-3 lg:h-4 lg:w-4" />
                  <span className="text-xs lg:text-sm">Images</span>
                </Button>
                
                <Button
                  onClick={handleDocumentUploadClick}
                  variant="outline"
                  size="sm"
                  disabled={isGenerating || externalLoading}
                  className="flex items-center gap-1"
                >
                  <Upload className="h-3 w-3 lg:h-4 lg:w-4" />
                  <span className="text-xs lg:text-sm">Documents</span>
                </Button>
                
              </div>
              <Button
                onClick={handleGenerate}
                disabled={(!prompt.trim() && selectedImages.length === 0 && selectedFiles.length === 0) || isGenerating || externalLoading}
                className="bg-primary hover:bg-primary/90 text-primary-foreground text-sm lg:text-base order-1 sm:order-2"
                size="sm"
              >
                {(isGenerating || externalLoading) ? (
                  <>
                    <Loader2 className="h-3 w-3 lg:h-4 lg:w-4 mr-1 lg:mr-2 animate-spin" />
                    <span>{(selectedImages.length > 0 || selectedFiles.length > 0) ? "Processing..." : "Generating..."}</span>
                  </>
                ) : (
                  <>
                    {(selectedImages.length > 0 || selectedFiles.length > 0) ? (
                      <Upload className="h-3 w-3 lg:h-4 lg:w-4 mr-1 lg:mr-2" />
                    ) : (
                      <Send className="h-3 w-3 lg:h-4 lg:w-4 mr-1 lg:mr-2" />
                    )}
                    <span>{(selectedImages.length > 0 || selectedFiles.length > 0) ? "Process Files" : "Generate SQL"}</span>
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
            <span className="text-sm text-muted-foreground">
              {(selectedImages.length > 0 || selectedFiles.length > 0) ? "AI is analyzing files..." : "AI is thinking..."}
            </span>
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
