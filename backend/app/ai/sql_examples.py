"""
Advanced SQL example bank for the AI SQL copilot.

Each example is a dict with these keys:
 - user_prompt: natural language prompt that might be given by a user
 - expected_sql: a complete, runnable SQL snippet (CREATEs, INSERTs, SELECTs) demonstrating the concept
 - reasoning: short explanation the model can use to shape answers

These examples intentionally show full CREATE/INSERT + SELECT so Gemini can return complete runnable scripts
on follow-ups or when asked for demonstrations.
"""

SQL_EXAMPLES = [
    {
        "user_prompt": "Find the top-selling product in each category using ROW_NUMBER()",
        "expected_sql": """-- schema & data
CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT NOT NULL);
CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT NOT NULL, category_id INTEGER, FOREIGN KEY(category_id) REFERENCES categories(id));
CREATE TABLE sales (id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL, qty INTEGER NOT NULL, sale_date DATE, FOREIGN KEY(product_id) REFERENCES products(id));

INSERT INTO categories (id, name) VALUES (1,'Electronics'),(2,'Books');
INSERT INTO products (id, name, category_id) VALUES (1,'Laptop',1),(2,'Smartphone',1),(3,'Novel',2),(4,'Anthology',2);
INSERT INTO sales (product_id, qty, sale_date) VALUES (1,5,'2024-01-01'),(1,3,'2024-01-02'),(2,7,'2024-01-03'),(3,10,'2024-01-02'),(4,2,'2024-01-05');

-- use ROW_NUMBER() partitioned by category to pick the top product per category
WITH product_sales AS (
  SELECT p.id AS product_id, p.name AS product_name, p.category_id, SUM(s.qty) AS total_qty
  FROM products p
  JOIN sales s ON p.id = s.product_id
  GROUP BY p.id, p.name, p.category_id
)
SELECT category_id, product_id, product_name, total_qty
FROM (
  SELECT ps.*, ROW_NUMBER() OVER (PARTITION BY ps.category_id ORDER BY ps.total_qty DESC) AS rn
  FROM product_sales ps
) t
WHERE rn = 1;
""",
        "reasoning": "ROW_NUMBER() with PARTITION BY category_id ranks products per category. Selecting rows where rn=1 returns the top-selling product for each category even when multiple categories exist."
    },

    {
        "user_prompt": "Show user spending ranks using RANK() and DENSE_RANK() to illustrate differences",
        "expected_sql": """-- setup
CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, total_amount REAL, FOREIGN KEY(user_id) REFERENCES users(id));

INSERT INTO users (id, name) VALUES (1,'Alice'),(2,'Bob'),(3,'Carol'),(4,'Dave');
INSERT INTO orders (user_id, total_amount) VALUES (1,100.0),(1,50.0),(2,150.0),(3,150.0),(4,30.0);

-- compute total per user then show RANK and DENSE_RANK side-by-side
WITH user_totals AS (
  SELECT u.id, u.name, COALESCE(SUM(o.total_amount),0) AS total_spent
  FROM users u
  LEFT JOIN orders o ON u.id = o.user_id
  GROUP BY u.id, u.name
)
SELECT id, name, total_spent,
       RANK() OVER (ORDER BY total_spent DESC)    AS rank_with_gaps,
       DENSE_RANK() OVER (ORDER BY total_spent DESC) AS dense_rank_no_gaps
FROM user_totals
ORDER BY total_spent DESC;
""",
        "reasoning": "RANK() leaves gaps when ties occur (e.g., totals 150,150 produce ranks 1 and 1 then next rank 3), while DENSE_RANK() assigns consecutive ranks (1,1,2). Showing both helps choose ranking semantics for business logic."
    },

    {
        "user_prompt": "Use LAG() and LEAD() to show previous and next month's sales per product",
        "expected_sql": """-- monthly sales per product
CREATE TABLE monthly_sales (id INTEGER PRIMARY KEY, product_id INTEGER, month TEXT, total_amount REAL);
INSERT INTO monthly_sales (product_id, month, total_amount) VALUES
  (1,'2024-01',100.0),(1,'2024-02',120.0),(1,'2024-03',90.0),
  (2,'2024-01',50.0),(2,'2024-02',60.0),(2,'2024-03',60.0);

-- show previous and next month's amounts (NULL if none)
SELECT product_id, month, total_amount,
       LAG(total_amount) OVER (PARTITION BY product_id ORDER BY month)   AS prev_month_amount,
       LEAD(total_amount) OVER (PARTITION BY product_id ORDER BY month)  AS next_month_amount,
       total_amount - LAG(total_amount) OVER (PARTITION BY product_id ORDER BY month) AS change_from_prev
FROM monthly_sales
ORDER BY product_id, month;
""",
        "reasoning": "LAG() and LEAD() are window functions that expose neighbor rows within a partition. They are ideal for time-series comparisons such as month-over-month changes."
    },

    {
        "user_prompt": "Show aggregate functions used with OVER() to compute per-row and partitioned aggregates",
        "expected_sql": """-- orders table example
CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, total_amount REAL);
INSERT INTO orders (user_id, total_amount) VALUES (1,100.0),(1,50.0),(2,200.0),(3,25.0),(2,50.0);

-- compute grand total, per-user total, and per-user order count alongside each order
SELECT id, user_id, total_amount,
       SUM(total_amount) OVER () AS grand_total,
       SUM(total_amount) OVER (PARTITION BY user_id) AS user_total,
       COUNT(*) OVER (PARTITION BY user_id) AS user_order_count,
       ROUND(100.0 * SUM(total_amount) OVER (PARTITION BY user_id) / NULLIF(SUM(total_amount) OVER (),0),2) AS pct_of_grand_total
FROM orders
ORDER BY user_id, id;
""",
        "reasoning": "Aggregate functions with OVER() compute running totals, partitioned aggregates, and global statistics without collapsing rows—useful for showing context with each row like percent-of-total and per-user counts."
    },

    {
        "user_prompt": "Demonstrate a self-join to list employees with their managers",
        "expected_sql": """-- employees with manager_id referencing same table (self-referential FK)
CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT NOT NULL, title TEXT, manager_id INTEGER, FOREIGN KEY(manager_id) REFERENCES employees(id));
INSERT INTO employees (id, name, title, manager_id) VALUES (1,'CEO','CEO',NULL),(2,'Alice','VP',1),(3,'Bob','Manager',2),(4,'Carol','Engineer',3);

-- self-join: alias employees twice to relate employee -> manager
SELECT e.id AS employee_id, e.name AS employee_name, e.title AS employee_title,
       m.id AS manager_id, m.name AS manager_name, m.title AS manager_title
FROM employees e
LEFT JOIN employees m ON e.manager_id = m.id
ORDER BY e.id;
""",
        "reasoning": "Self-joins use the same table twice (different aliases) to express hierarchical relationships like employee -> manager. LEFT JOIN ensures top-level rows with no manager still appear."
    },

    {
        "user_prompt": "Show CROSS JOIN usage: generate product × promotion date combinations",
        "expected_sql": """-- products and promotion_dates
CREATE TABLE products (id INTEGER PRIMARY KEY, name TEXT);
CREATE TABLE promotion_dates (promo_date DATE);
INSERT INTO products (id, name) VALUES (1,'Laptop'),(2,'Mouse');
INSERT INTO promotion_dates (promo_date) VALUES ('2024-12-01'),('2024-12-15');

-- CROSS JOIN produces Cartesian product (every product with every promo_date)
SELECT p.id AS product_id, p.name AS product_name, d.promo_date
FROM products p
CROSS JOIN promotion_dates d
ORDER BY p.id, d.promo_date;
""",
        "reasoning": "CROSS JOIN produces the Cartesian product. It is useful for planning or generating all combinations (e.g., product × promotion date). Use carefully—size grows multiplicatively."
    },

    {
        "user_prompt": "Normalize a flat orders table into 1NF, 2NF and 3NF (show transformed schema)",
        "expected_sql": """-- starting point (conceptual): orders_flat(order_id, customer_name, customer_email, item_sku, item_name, item_price, qty, order_date)
-- 1NF: ensure atomic values (no repeating item columns) -> represent each item as a separate row (order_items)
-- 2NF: move customer attributes to customers table (remove partial dependency on part of composite key)
-- 3NF: remove transitive dependencies (e.g., product price moved to products)

-- normalized schema
CREATE TABLE customers (id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL);
CREATE TABLE products (id INTEGER PRIMARY KEY, sku TEXT UNIQUE NOT NULL, name TEXT, price REAL);
CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL, order_date DATE, FOREIGN KEY(customer_id) REFERENCES customers(id));
CREATE TABLE order_items (id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL, product_id INTEGER NOT NULL, qty INTEGER NOT NULL, unit_price REAL NOT NULL,
  FOREIGN KEY(order_id) REFERENCES orders(id),
  FOREIGN KEY(product_id) REFERENCES products(id)
);

-- short example data to demonstrate relations
INSERT INTO customers (id, name, email) VALUES (1,'Alice','alice@example.com');
INSERT INTO products (id, sku, name, price) VALUES (1,'SKU-001','Novel',19.99);
INSERT INTO orders (id, customer_id, order_date) VALUES (100,1,'2024-01-01');
INSERT INTO order_items (order_id, product_id, qty, unit_price) VALUES (100,1,2,19.99);

-- Example query to reconstruct a single order with items
SELECT o.id AS order_id, c.name AS customer_name, c.email, o.order_date, oi.qty, p.sku, p.name AS product_name, oi.unit_price
FROM orders o
JOIN customers c ON c.id = o.customer_id
JOIN order_items oi ON oi.order_id = o.id
JOIN products p ON p.id = oi.product_id
WHERE o.id = 100;
""",
        "reasoning": "Shows stepwise normalization: 1NF (atomic item rows), 2NF (move customer attributes into customers table), 3NF (product attributes live in products). The example creates normalized tables and demonstrates reconstructing the original order via joins."
    },

    {
        "user_prompt": "Demonstrate UNION, UNION ALL, INTERSECT, and EXCEPT between two customer sets",
        "expected_sql": """-- two regional customer tables (same schema)
CREATE TABLE customers_us (id INTEGER PRIMARY KEY, email TEXT UNIQUE, name TEXT);
CREATE TABLE customers_eu (id INTEGER PRIMARY KEY, email TEXT UNIQUE, name TEXT);

INSERT INTO customers_us (id, email, name) VALUES (1,'a@example.com','Alice'),(2,'b@example.com','Bob'),(3,'c@example.com','Carol');
INSERT INTO customers_eu (id, email, name) VALUES (10,'b@example.com','Bob'),(11,'d@example.com','Dora'),(12,'e@example.com','Eve');

-- UNION: distinct union across both sets (deduplicates duplicate rows)
SELECT email, name FROM customers_us
UNION
SELECT email, name FROM customers_eu
ORDER BY email;

-- UNION ALL: keeps duplicates (faster, preserves all rows)
SELECT email, name FROM customers_us
UNION ALL
SELECT email, name FROM customers_eu
ORDER BY email;

-- INTERSECT: emails present in both regions (common set)
SELECT email, name FROM customers_us
INTERSECT
SELECT email, name FROM customers_eu;

-- EXCEPT: in US but not in EU (US \ EU)
SELECT email, name FROM customers_us
EXCEPT
SELECT email, name FROM customers_eu;
""",
        "reasoning": "Set operators operate on whole-row-compatible SELECTs: UNION merges and deduplicates, UNION ALL merges without deduplication, INTERSECT returns intersection, EXCEPT returns rows in the first set not in the second. Useful for regional deduplication and difference checks."
    },

    {
        "user_prompt": "Compute a 3-row moving average using a window frame (ROWS BETWEEN)",
        "expected_sql": """-- daily sales and moving average with frame
CREATE TABLE daily_sales (id INTEGER PRIMARY KEY, sale_date DATE, total_amount REAL);
INSERT INTO daily_sales (sale_date, total_amount) VALUES ('2024-01-01',10.0),('2024-01-02',20.0),('2024-01-03',30.0),('2024-01-04',40.0),('2024-01-05',50.0);

SELECT sale_date, total_amount,
       ROUND(AVG(total_amount) OVER (ORDER BY sale_date ROWS BETWEEN 2 PRECEDING AND CURRENT ROW),2) AS moving_avg_3
FROM daily_sales
ORDER BY sale_date;
""",
        "reasoning": "Window frame 'ROWS BETWEEN 2 PRECEDING AND CURRENT ROW' computes a 3-row moving average. This is a deterministic, row-count-based frame useful for smoothing time-series data."
    },

    {
        "user_prompt": "Find pairs of colleagues in the same department using a self-join (exclude self-pairs)",
        "expected_sql": """-- department colleagues using self-join
CREATE TABLE employees (id INTEGER PRIMARY KEY, name TEXT, department_id INTEGER);
INSERT INTO employees (id, name, department_id) VALUES (1,'Alice',10),(2,'Bob',10),(3,'Carol',20),(4,'Dave',10);

-- find ordered pairs of employees in the same dept (exclude identity pairs)
SELECT e1.id AS emp1_id, e1.name AS emp1_name, e2.id AS emp2_id, e2.name AS emp2_name, e1.department_id
FROM employees e1
JOIN employees e2 ON e1.department_id = e2.department_id AND e1.id < e2.id
ORDER BY e1.department_id, e1.id;
""",
        "reasoning": "Self-join finds relationships between rows in the same table. Using a conditional like e1.id < e2.id avoids duplicate swapped pairs and self-pairings."
    },

    {
        "user_prompt": "Show percent contribution of each order to its user's total using OVER(PARTITION BY)",
        "expected_sql": """-- percent of user's total per order
CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, total_amount REAL);
INSERT INTO orders (user_id, total_amount) VALUES (1,100.0),(1,50.0),(2,200.0),(2,100.0);

SELECT id, user_id, total_amount,
       ROUND(100.0 * total_amount / NULLIF(SUM(total_amount) OVER (PARTITION BY user_id),0),2) AS pct_of_user_total
FROM orders
ORDER BY user_id, id;
""",
        "reasoning": "Partitioned aggregate (SUM(...) OVER (PARTITION BY user_id)) lets you compute each order's share of that user's total without grouping away individual orders."
    }
]


def get_examples_context(max_examples: int = 6) -> str:
    """
    Return a compact text block of the top N examples to include in prompts.
    Keeps SQL one-line per example to limit prompt size while preserving intent.
    """
    parts = ["Advanced SQL examples (compact):\n"]
    for i, ex in enumerate(SQL_EXAMPLES[:max_examples], start=1):
        sql_one_line = " ".join(line.strip() for line in ex["expected_sql"].splitlines() if line.strip())
        parts.append(f"Example {i}:")
        parts.append(f"User: \"{ex['user_prompt']}\"")
        parts.append(f"SQL: {sql_one_line[:1200]}")  # truncate extremely long SQL in context block
        parts.append(f"Reasoning: {ex['reasoning']}\n")
    return "\n".join(parts)
