# ER Diagram Feature Test

This document shows how to test the new ER diagram feature in AutoSQL.

## Backend Testing

1. **Start the backend server:**
   ```bash
   cd backend
   python -m uvicorn main:app --reload
   ```

2. **Test the schema endpoint:**
   ```bash
   curl http://localhost:8000/api/db/schema/mermaid
   ```

## Frontend Testing

1. **Start the frontend server:**
   ```bash
   cd frontend
   npm run dev
   ```

2. **Access the ER diagram page:**
   - Click the "ER Diagram" button in the sidebar, or
   - Navigate directly to: http://localhost:3000/er-diagram

## Expected Behavior

### When Database is Empty
- Shows "No Database Schema Found" message
- Provides button to go back to main page to create tables

### When Database Has Tables
- Generates Mermaid ER diagram code
- Displays the code in a formatted code block
- Provides link to mermaid.live for visual rendering

## Example Schema to Test With

Go to the main page and execute these SQL statements to create test tables:

```sql
CREATE TABLE departments (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    manager_id INTEGER
);

CREATE TABLE employees (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    salary INTEGER,
    department_id INTEGER,
    FOREIGN KEY (department_id) REFERENCES departments(id)
);

CREATE TABLE projects (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    budget REAL,
    department_id INTEGER,
    FOREIGN KEY (department_id) REFERENCES departments(id)
);
```

## Expected Mermaid Output

The ER diagram endpoint should return something like:

```mermaid
erDiagram
    departments {
        INTEGER id PK
        TEXT name NOT_NULL
        INTEGER manager_id
    }
    employees {
        INTEGER id PK
        TEXT name NOT_NULL
        TEXT email NOT_NULL
        INTEGER salary
        INTEGER department_id
    }
    projects {
        INTEGER id PK
        TEXT title NOT_NULL
        REAL budget
        INTEGER department_id
    }
    employees }o--|| departments : "department_id_to_id"
    projects }o--|| departments : "department_id_to_id"
```

## Features Implemented

✅ Backend schema introspection with SQLAlchemy
✅ Mermaid ER diagram code generation
✅ RESTful API endpoint `/api/db/schema/mermaid`
✅ Frontend page with error handling
✅ Navigation integration in sidebar
✅ Empty state handling
✅ Responsive design
✅ TypeScript support

## Future Enhancements

- [ ] Install proper Mermaid renderer for visual diagrams
- [ ] Add schema export functionality
- [ ] Include table statistics and metadata
- [ ] Support for views and stored procedures
- [ ] Interactive diagram editing