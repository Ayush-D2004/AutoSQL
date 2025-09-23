# AutoSQL 🚀

AutoSQL is an AI-powered SQL query generator that transforms natural language prompts into executable SQL queries. Built with modern web technologies and Google's Gemini AI, it provides an intuitive interface for database operations, schema visualization, and multimodal data processing.

## ✨ Features

### 🤖 AI-Powered SQL Generation
- **Natural Language to SQL**: Convert plain English descriptions into precise SQL queries
- **Multimodal Input Support**: Process text prompts, images, and document files (.sql, .json, .xlsx, .csv)
- **Context-Aware**: Understands your database schema for accurate query generation

### 📊 Database Management
- **Interactive Query Execution**: Run queries with real-time results display
- **Multi-Table Results**: Handle complex queries returning multiple result sets
- **Schema Visualization**: Generate ER diagrams and Mindmaps of your database structure

## 🛠️ Tech Stack

### Frontend
- **Next.js 14** - React framework with App Router
- **TypeScript** - Type-safe development
- **Tailwind CSS** - Utility-first styling
- **Framer Motion** - Smooth animations
- **Radix UI** - Accessible component primitives
- **Mermaid** - Diagram and flowchart generation

### Backend
- **FastAPI** - Modern Python web framework
- **SQLAlchemy** - Database ORM with async support
- **SQLite** - Lightweight database engine
- **Google Gemini AI** - Multimodal AI processing
- **LangGraph** - AI workflow orchestration
- **Pandas** - Data processing and analysis

## 🚀 Quick Start

### Prerequisites
- **Node.js** 18+ and npm
- **Python** 3.8+
- **Google API Key** for Gemini AI

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/Ayush-D2004/AutoSQL.git
cd AutoSQL
```

2. **Backend Setup**
```bash
cd backend
python -m venv autosql
autosql/bin/activate

pip install -r requirements.txt

echo "GOOGLE_API_KEY=your_gemini_api_key_here" > .env
echo "GEMINI_MODEL=gemini-1.5-flash" >> .env
```

3. **Frontend Setup**
```bash
cd frontend
npm install

echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
```

### Running the Application

1. **Start the Backend**
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

2. **Start the Frontend**
```bash
cd frontend
npm run dev
```

## 🔧 Configuration

### Environment Variables

**Backend (.env)**
```env
GOOGLE_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
DATABASE_URL=sqlite:///./autosql.db
LOG_LEVEL=INFO
```

**Frontend (.env.local)**
```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### Google Gemini API Setup
1. Visit [Google AI Studio](https://aistudio.google.com/)
2. Create a new project or select existing one
3. Generate an API key
4. Add the key to your backend `.env` file

**Made with ❤️ by [Ayush-D2004](https://github.com/Ayush-D2004)**