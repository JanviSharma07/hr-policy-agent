-- Queries to show the Humanly database in pgAdmin (Query Tool) or psql.
-- Run them one at a time: select a query and press F5 (pgAdmin) or paste it into psql.

-- 1. Every employee with their department, skills and grade
SELECT id, email, role, department, job_title, grade, city, join_date, skills
FROM users
ORDER BY role DESC, department, email;

-- 2. Headcount per department
SELECT COALESCE(department, 'Not set') AS department, COUNT(*) AS employees
FROM users
WHERE role = 'employee'
GROUP BY department
ORDER BY employees DESC;

-- 3. Policy documents and their versions (archived = replaced by a newer version)
SELECT family_id, title, version, CASE WHEN is_active THEN 'current' ELSE 'archived' END AS status,
       chunk_count, uploaded_at
FROM documents
ORDER BY family_id, uploaded_at;

-- 4. Questions asked, which agent answered, and the 👍 / 👎 rating
SELECT u.email, u.department, q.content AS question, a.intent,
       CASE a.feedback WHEN 1 THEN 'helpful' WHEN -1 THEN 'not helpful' ELSE '-' END AS rating,
       a.created_at
FROM messages a
JOIN messages q ON q.conversation_id = a.conversation_id
              AND q.id = (SELECT MAX(id) FROM messages WHERE conversation_id = a.conversation_id
                          AND sender = 'user' AND id < a.id)
JOIN conversations c ON c.id = a.conversation_id
JOIN users u ON u.id = c.user_id
WHERE a.sender = 'assistant'
ORDER BY a.created_at DESC;

-- 5. HR Inbox: private requests and questions Humanly couldn't answer
SELECT r.id, u.email, r.department, r.kind, r.topic, r.question, r.status,
       r.reply, r.added_to_knowledge, r.created_at
FROM hr_requests r
JOIN users u ON u.id = r.user_id
ORDER BY r.created_at DESC;

-- 6. Holiday calendar
SELECT day, TO_CHAR(day, 'Dy') AS weekday, name, kind
FROM holidays
ORDER BY day;
