import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'
import { authAPI, chatAPI, documentsAPI, holidaysAPI, hrAPI, requestsAPI, systemAPI } from './services/api'

// Same list as DEPARTMENTS in backend/app/routes/auth.py
const departments = ['Engineering', 'Sales', 'Marketing', 'Finance', 'Human Resources', 'Operations', 'Customer Support', 'Legal']

const suggestions = [
  {
    icon: '🏖️',
    title: 'Leave & holidays',
    description: 'Understand leave policies and holiday entitlements.',
    prompt: 'How many casual leaves do I get?',
  },
  {
    icon: '💰',
    title: 'Travel & reimbursements',
    description: 'Work out what you can claim for official travel.',
    prompt: 'How much do I get for a 400 km trip by car?',
  },
  {
    icon: '🏢',
    title: 'Workplace policies',
    description: 'See what changed between policy versions.',
    prompt: 'What changed in the work from home policy?',
  },
  {
    icon: '📋',
    title: 'Employee eligibility',
    description: 'Check what you qualify for, based on your profile.',
    prompt: 'Am I eligible for earned leave?',
  },
]

const policyCategories = [
  {
    icon: '🏖️',
    title: 'Leave & attendance',
    description: 'Leave entitlements, holidays and attendance guidelines.',
    prompt: 'Summarize the leave policy',
  },
  {
    icon: '💰',
    title: 'Travel & reimbursement',
    description: 'Mileage, daily allowance, hotels and claim rules.',
    prompt: 'Summarize the travel policy',
  },
  {
    icon: '🏠',
    title: 'Work from home',
    description: 'Who can work from home, how often and allowances.',
    prompt: 'Summarize the work from home policy',
  },
  {
    icon: '🛡️',
    title: 'Employee guidelines',
    description: 'Eligibility, employee responsibilities and general guidance.',
    prompt: 'What should I know before applying for leave?',
  },
]

function shortTitle(text) {
  return text.length > 36 ? `${text.slice(0, 36)}…` : text
}

function initials(email = '') {
  return (email[0] || 'U').toUpperCase()
}

function displayName(email = '') {
  const name = email.split('@')[0] || 'User'
  return name.charAt(0).toUpperCase() + name.slice(1)
}

function monthsOfService(joinDate) {
  if (!joinDate) return null
  const join = new Date(`${joinDate}T00:00:00`)
  const today = new Date()
  let months = (today.getFullYear() - join.getFullYear()) * 12 + (today.getMonth() - join.getMonth())
  if (today.getDate() < join.getDate()) months -= 1
  return Math.max(months, 0)
}

function formatDate(value) {
  if (!value) return ''
  return new Date(value).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

/* ---------- Login / register ---------- */

function AuthScreen({ onLoggedIn, backendOnline }) {
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ email: '', password: '', join_date: '', department: '', job_title: '', city: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  function update(field, value) {
    setForm((previous) => ({ ...previous, [field]: value }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      if (mode === 'register') {
        await authAPI.register({
          email: form.email.trim(),
          password: form.password,
          join_date: form.join_date || null,
          department: form.department || null,
          job_title: form.job_title.trim() || null,
          city: form.city.trim() || null,
        })
      }
      await authAPI.login(form.email.trim(), form.password)
      onLoggedIn(await authAPI.getProfile())
    } catch (err) {
      setError(err.message || 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-shell">
      <form className="auth-card" onSubmit={handleSubmit}>
        <div className="sidebar-brand auth-brand">
          <div className="brand-mark">H</div>
          <div className="brand-copy">
            <span className="brand-name">HUMANLY</span>
            <span className="brand-caption">HR INTELLIGENCE</span>
          </div>
        </div>

        <h1>{mode === 'login' ? 'Welcome back' : 'Create your account'}</h1>
        <p className="auth-subtitle">
          {mode === 'login'
            ? 'Sign in to ask questions about your HR policies.'
            : 'Your department, joining date and city let HUMANLY answer eligibility and allowance questions for you.'}
        </p>

        <label className="form-field">
          <span>Work email</span>
          <input type="email" required value={form.email} onChange={(e) => update('email', e.target.value)} placeholder="you@company.com" />
        </label>

        <label className="form-field">
          <span>Password</span>
          <input type="password" required value={form.password} onChange={(e) => update('password', e.target.value)} placeholder="••••••••" />
        </label>

        {mode === 'register' && (
          <>
            <div className="form-row">
              <label className="form-field">
                <span>Department</span>
                <select value={form.department} onChange={(e) => update('department', e.target.value)}>
                  <option value="">Select…</option>
                  {departments.map((d) => <option key={d}>{d}</option>)}
                </select>
              </label>
              <label className="form-field">
                <span>Job title</span>
                <input value={form.job_title} onChange={(e) => update('job_title', e.target.value)} placeholder="e.g. Software Engineer" />
              </label>
            </div>
            <div className="form-row">
              <label className="form-field">
                <span>Joining date</span>
                <input type="date" value={form.join_date} onChange={(e) => update('join_date', e.target.value)} />
              </label>
              <label className="form-field">
                <span>City</span>
                <input value={form.city} onChange={(e) => update('city', e.target.value)} placeholder="e.g. Bengaluru" />
              </label>
            </div>
          </>
        )}

        {error && <p className="form-error">{error}</p>}
        {!backendOnline && (
          <p className="form-error">Can't reach the backend. Start it with: uvicorn app.main:app --reload</p>
        )}

        <button className="return-button auth-submit" type="submit" disabled={busy}>
          {busy ? 'Please wait…' : mode === 'login' ? 'Sign in →' : 'Create account →'}
        </button>

        <p className="auth-switch">
          {mode === 'login' ? 'New here?' : 'Already have an account?'}{' '}
          <button type="button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError('') }}>
            {mode === 'login' ? 'Create an account' : 'Sign in'}
          </button>
        </p>
      </form>
    </div>
  )
}

/* ---------- One answer: text, citations and agent steps ---------- */

function Citations({ citations }) {
  const [openIndex, setOpenIndex] = useState(null)
  if (!citations?.length) return null

  return (
    <div className="citations">
      <span className="citations-label">Sources</span>
      <div className="citation-list">
        {citations.map((citation, index) => (
          <button
            key={`${citation.document_id}-${citation.section}-${index}`}
            className={`citation-chip ${openIndex === index ? 'citation-chip-open' : ''}`}
            onClick={() => setOpenIndex(openIndex === index ? null : index)}
            title="Show the source text"
          >
            {citation.title} · v{citation.version}
            {citation.status === 'archived' && <span className="citation-archived">archived</span>}
            <span className="citation-section">
              {citation.section}
              {citation.page ? ` · p.${citation.page}` : ''}
            </span>
          </button>
        ))}
      </div>
      {openIndex !== null && citations[openIndex]?.text && (
        <blockquote className="citation-text">{citations[openIndex].text}</blockquote>
      )}
    </div>
  )
}

function AgentTrace({ steps, live }) {
  if (!steps?.length) return null
  if (live) {
    return (
      <ul className="trace-list trace-live">
        {steps.map((step, index) => (
          <li key={index}>{step}</li>
        ))}
      </ul>
    )
  }
  return (
    <details className="trace">
      <summary>How I got this answer</summary>
      <ul className="trace-list">
        {steps.map((step, index) => (
          <li key={index}>{step}</li>
        ))}
      </ul>
    </details>
  )
}

/* ---------- Thumbs up / down on an answer ---------- */

function Feedback({ messageId, value, onChange }) {
  const [busy, setBusy] = useState(false)
  if (!messageId) return null

  async function rate(next) {
    const newValue = value === next ? 0 : next // clicking the same button again removes the rating
    setBusy(true)
    try {
      await chatAPI.sendFeedback(messageId, newValue)
      onChange(newValue || null)
    } catch {
      // a failed rating shouldn't interrupt the chat
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="feedback-row">
      <span className="feedback-label">{value ? 'Thanks for the feedback' : 'Was this helpful?'}</span>
      <button className={`feedback-button ${value === 1 ? 'feedback-up' : ''}`} disabled={busy} onClick={() => rate(1)} aria-label="Helpful" title="Helpful">
        👍
      </button>
      <button className={`feedback-button ${value === -1 ? 'feedback-down' : ''}`} disabled={busy} onClick={() => rate(-1)} aria-label="Not helpful" title="Not helpful">
        👎
      </button>
    </div>
  )
}

/* ---------- Skill tags: type a skill and press Enter or comma ---------- */

function SkillsInput({ skills, onChange }) {
  const [draft, setDraft] = useState('')

  function add() {
    const skill = draft.trim().replace(/,$/, '')
    if (skill && !skills.some((s) => s.toLowerCase() === skill.toLowerCase())) onChange([...skills, skill])
    setDraft('')
  }

  return (
    <div className="skills-input">
      {skills.map((skill) => (
        <span className="skill-chip" key={skill}>
          {skill}
          <button type="button" onClick={() => onChange(skills.filter((s) => s !== skill))} aria-label={`Remove ${skill}`}>×</button>
        </span>
      ))}
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ',') {
            e.preventDefault()
            add()
          } else if (e.key === 'Backspace' && !draft && skills.length) {
            onChange(skills.slice(0, -1))
          }
        }}
        onBlur={add}
        placeholder={skills.length ? 'Add another…' : 'Type a skill and press Enter'}
      />
    </div>
  )
}

function SkillChips({ skills }) {
  if (!skills?.length) return <span className="form-hint">No skills added yet</span>
  return (
    <div className="skill-list">
      {skills.map((skill) => <span className="skill-chip skill-chip-static" key={skill}>{skill}</span>)}
    </div>
  )
}

/* ---------- Profile page ---------- */

function ProfilePage({ user, onSaved, onLogout }) {
  const [form, setForm] = useState({
    job_title: user.job_title || '',
    city: user.city || '',
    skills: user.skills || [],
  })
  const [status, setStatus] = useState('')

  async function save(event) {
    event.preventDefault()
    setStatus('Saving…')
    try {
      const updated = await authAPI.updateProfile({
        job_title: form.job_title.trim() || null,
        city: form.city.trim() || null,
        skills: form.skills,
      })
      onSaved(updated)
      setStatus('Saved ✓')
    } catch (err) {
      setStatus(err.message)
    }
  }

  const months = monthsOfService(user.join_date)

  return (
    <section className="activity-page">
      <div className="page-heading">
        <span className="welcome-eyebrow">YOUR ACCOUNT</span>
        <h1>My profile</h1>
        <p>HUMANLY uses your department, joining date and city to answer eligibility and allowance questions for you.</p>
      </div>

      <div className="profile-hero panel-card">
        <div className="profile-hero-avatar">{initials(user.email)}</div>
        <div className="profile-hero-copy">
          <h2>{displayName(user.email)}</h2>
          <p className="profile-hero-title">
            {[user.job_title, user.department].filter(Boolean).join(' · ') || (user.role === 'hr_admin' ? 'HR admin' : 'Employee')}
          </p>
          <div className="profile-hero-meta">
            {user.department && <span className="dept-badge">{user.department}</span>}
            {user.city && <span>📍 {user.city}</span>}
            {user.join_date && <span>🗓 Joined {formatDate(user.join_date)}</span>}
            {months !== null && <span>⏱ {months} month{months === 1 ? '' : 's'} of service</span>}
          </div>
          <SkillChips skills={user.skills} />
        </div>
      </div>

      <form className="panel-card" onSubmit={save}>
        <h2 className="panel-title">Edit your details</h2>
        <div className="form-row">
          <label className="form-field">
            <span>Email</span>
            <input value={user.email} disabled />
          </label>
          <label className="form-field">
            <span>Department <em className="field-note">managed by HR</em></span>
            <input value={user.department || 'Not set'} disabled />
          </label>
          <label className="form-field">
            <span>Joining date <em className="field-note">managed by HR</em></span>
            <input value={user.join_date ? formatDate(user.join_date) : 'Not set'} disabled />
          </label>
        </div>
        <div className="form-row">
          <label className="form-field">
            <span>Job title</span>
            <input value={form.job_title} onChange={(e) => setForm({ ...form, job_title: e.target.value })} placeholder="e.g. Software Engineer" />
          </label>
          <label className="form-field">
            <span>City</span>
            <input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} placeholder="e.g. Bengaluru" />
          </label>
        </div>
        <div className="form-field">
          <span>Skills</span>
          <SkillsInput skills={form.skills} onChange={(skills) => setForm({ ...form, skills })} />
        </div>

        <div className="panel-actions">
          <button className="return-button" type="submit">Save profile</button>
          <span className="form-hint">{status}</span>
          <button className="ghost-button" type="button" onClick={onLogout}>Sign out</button>
        </div>
      </form>
    </section>
  )
}

/* ---------- HR: employee directory ---------- */

function EmployeesPage({ onAuthError }) {
  const [employees, setEmployees] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [query, setQuery] = useState('')
  const [departmentFilter, setDepartmentFilter] = useState('')
  const [editing, setEditing] = useState(null) // { id, ...fields }
  const [savingId, setSavingId] = useState(null)

  const load = useCallback(async () => {
    try {
      setEmployees(await hrAPI.getEmployees())
      setError('')
    } catch (err) {
      if (err.status === 401) onAuthError()
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [onAuthError])

  useEffect(() => {
    load()
  }, [load])

  function startEdit(emp) {
    setEditing({
      id: emp.id,
      department: emp.department || '',
      job_title: emp.job_title || '',
      grade: emp.grade || '',
      city: emp.city || '',
      join_date: emp.join_date || '',
      skills: emp.skills || [],
    })
  }

  async function saveEdit(event) {
    event.preventDefault()
    setSavingId(editing.id)
    try {
      const { id, ...fields } = editing
      const updated = await hrAPI.updateEmployee(id, { ...fields, join_date: fields.join_date || null })
      setEmployees((list) => list.map((e) => (e.id === id ? { ...e, ...updated } : e)))
      setEditing(null)
    } catch (err) {
      if (err.status === 401) onAuthError()
      setError(err.message)
    } finally {
      setSavingId(null)
    }
  }

  const q = query.toLowerCase().trim()
  const visible = employees.filter((e) => {
    if (departmentFilter && e.department !== departmentFilter) return false
    if (!q) return true
    return [e.email, e.job_title, e.department, e.city, ...(e.skills || [])]
      .filter(Boolean)
      .some((value) => value.toLowerCase().includes(q))
  })
  const departmentCount = new Set(employees.map((e) => e.department).filter(Boolean)).size

  return (
    <section className="activity-page">
      <div className="page-heading">
        <span className="welcome-eyebrow">HR ADMIN</span>
        <h1>Employees</h1>
        <p>Everyone in the company, with their department and skills. Grades are only visible here; HUMANLY uses them for travel and allowance rules.</p>
      </div>

      <div className="activity-stats">
        <div className="activity-stat">
          <span>Total people</span>
          <strong>{employees.length}</strong>
        </div>
        <div className="activity-stat">
          <span>Departments</span>
          <strong>{departmentCount}</strong>
        </div>
        <div className="activity-stat">
          <span>Questions asked</span>
          <strong>{employees.reduce((sum, e) => sum + (e.questions_asked || 0), 0)}</strong>
        </div>
      </div>

      <div className="directory-toolbar">
        <label className="library-search directory-search">
          <span>⌕</span>
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by name, skill, city or job title…" />
        </label>
        <select className="directory-filter" value={departmentFilter} onChange={(e) => setDepartmentFilter(e.target.value)}>
          <option value="">All departments</option>
          {departments.map((d) => <option key={d}>{d}</option>)}
        </select>
      </div>

      {error && <p className="notice notice-error">{error}</p>}

      {loading ? (
        <p className="form-hint">Loading…</p>
      ) : visible.length === 0 ? (
        <div className="activity-empty">
          <span>☺</span>
          <h3>No one matches</h3>
          <p>Try a different search or department.</p>
        </div>
      ) : (
        <div className="employee-grid">
          {visible.map((emp) =>
            editing?.id === emp.id ? (
              <form className="employee-card employee-card-editing" key={emp.id} onSubmit={saveEdit}>
                <div className="employee-card-top">
                  <div className="avatar">{initials(emp.email)}</div>
                  <div>
                    <h3>{displayName(emp.email)}</h3>
                    <p>{emp.email}</p>
                  </div>
                </div>
                <div className="form-row">
                  <label className="form-field">
                    <span>Department</span>
                    <select value={editing.department} onChange={(e) => setEditing({ ...editing, department: e.target.value })}>
                      <option value="">Not set</option>
                      {departments.map((d) => <option key={d}>{d}</option>)}
                    </select>
                  </label>
                  <label className="form-field">
                    <span>Grade</span>
                    <input value={editing.grade} onChange={(e) => setEditing({ ...editing, grade: e.target.value })} placeholder="e.g. L3" />
                  </label>
                </div>
                <div className="form-row">
                  <label className="form-field">
                    <span>Job title</span>
                    <input value={editing.job_title} onChange={(e) => setEditing({ ...editing, job_title: e.target.value })} />
                  </label>
                  <label className="form-field">
                    <span>City</span>
                    <input value={editing.city} onChange={(e) => setEditing({ ...editing, city: e.target.value })} />
                  </label>
                </div>
                <label className="form-field">
                  <span>Joining date</span>
                  <input type="date" value={editing.join_date} onChange={(e) => setEditing({ ...editing, join_date: e.target.value })} />
                </label>
                <div className="form-field">
                  <span>Skills</span>
                  <SkillsInput skills={editing.skills} onChange={(skills) => setEditing({ ...editing, skills })} />
                </div>
                <div className="panel-actions">
                  <button className="return-button" type="submit" disabled={savingId === emp.id}>
                    {savingId === emp.id ? 'Saving…' : 'Save'}
                  </button>
                  <button className="ghost-button" type="button" onClick={() => setEditing(null)}>Cancel</button>
                </div>
              </form>
            ) : (
              <div className="employee-card" key={emp.id}>
                <div className="employee-card-top">
                  <div className="avatar">{initials(emp.email)}</div>
                  <div className="employee-card-name">
                    <h3>{displayName(emp.email)}</h3>
                    <p>{emp.job_title || (emp.role === 'hr_admin' ? 'HR admin' : 'Employee')}</p>
                  </div>
                  {emp.grade && <span className="grade-badge" title="Grade (only HR can see this)">{emp.grade}</span>}
                </div>
                <div className="employee-meta">
                  {emp.department ? <span className="dept-badge">{emp.department}</span> : <span className="dept-badge dept-badge-empty">No department</span>}
                  {emp.city && <span>📍 {emp.city}</span>}
                  {emp.join_date && <span>⏱ {monthsOfService(emp.join_date)} mo</span>}
                </div>
                <SkillChips skills={emp.skills} />
                <div className="employee-card-bottom">
                  <span>{emp.questions_asked} question{emp.questions_asked === 1 ? '' : 's'} asked</span>
                  <button className="activity-open-button" onClick={() => startEdit(emp)}>Edit</button>
                </div>
              </div>
            ),
          )}
        </div>
      )}
    </section>
  )
}

/* ---------- HR: insights dashboard ---------- */

function BarList({ items, empty }) {
  if (!items?.length) return <p className="form-hint">{empty}</p>
  const max = Math.max(...items.map((i) => i.count))
  return (
    <div className="bar-list">
      {items.map((item) => (
        <div className="bar-row" key={item.label}>
          <span className="bar-label">{item.label}</span>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${Math.max((item.count / max) * 100, 4)}%` }} />
          </div>
          <span className="bar-count">{item.count}</span>
        </div>
      ))}
    </div>
  )
}

function InsightsPage({ onAuthError, onAskAbout, onOpenInbox }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(async () => {
    setRefreshing(true)
    try {
      setData(await hrAPI.getInsights())
      setError('')
    } catch (err) {
      if (err.status === 401) onAuthError()
      setError(err.message)
    } finally {
      setRefreshing(false)
    }
  }, [onAuthError])

  useEffect(() => {
    load()
  }, [load])

  const t = data?.totals

  return (
    <section className="activity-page">
      <div className="page-heading heading-with-action">
        <div>
          <span className="welcome-eyebrow">HR ADMIN</span>
          <h1>Insights</h1>
          <p>What employees ask, how useful the answers are, and which questions your policies don't cover yet.</p>
        </div>
        <button className="ghost-button" onClick={load} disabled={refreshing}>{refreshing ? 'Refreshing…' : '↻ Refresh'}</button>
      </div>

      {error && <p className="notice notice-error">{error}</p>}
      {!data ? (
        <p className="form-hint">Loading…</p>
      ) : (
        <>
          <div className="insight-stats">
            <div className="activity-stat">
              <span>Questions answered</span>
              <strong>{t.questions}</strong>
              <p>from {t.employees_asking} {t.employees_asking === 1 ? 'person' : 'people'}</p>
            </div>
            <div className="activity-stat">
              <span>Helpful rating</span>
              <strong>{t.helpful_rate === null ? '–' : `${t.helpful_rate}%`}</strong>
              <p>👍 {t.helpful} · 👎 {t.not_helpful}</p>
            </div>
            <div className="activity-stat">
              <span>Not covered by any policy</span>
              <strong className={t.unanswered ? 'stat-warn' : ''}>{t.unanswered}</strong>
              <p>policy gaps to review</p>
            </div>
          </div>

          <div className="insight-grid">
            <div className="panel-card">
              <h2 className="panel-title">What employees ask about</h2>
              <p className="panel-sub">Which agent handled each question (from the DistilBERT router)</p>
              <BarList items={data.by_intent} empty="No questions yet." />
            </div>
            <div className="panel-card">
              <h2 className="panel-title">Questions by department</h2>
              <p className="panel-sub">Where the demand for HR answers comes from</p>
              <BarList items={data.by_department} empty="No questions yet." />
            </div>
          </div>

          <div className="panel-card">
            <h2 className="panel-title">⚠ Questions no policy could answer</h2>
            <p className="panel-sub">Each one is a gap in your policies. Answer it in the HR Inbox (and teach Humanly), or add a policy that covers it.</p>
            {data.unanswered.length === 0 ? (
              <p className="form-hint">None so far. Every question was answered from a policy.</p>
            ) : (
              <ul className="insight-list">
                {data.unanswered.map((item, i) => (
                  <li key={i}>
                    <span className="insight-question">“{item.question}”</span>
                    <span className="insight-meta">
                      {item.department} · {formatDate(item.asked_at)} ·{' '}
                      {item.hr_replied
                        ? <span className="replied-tag">✓ HR replied</span>
                        : <button className="link-button" onClick={onOpenInbox}>Answer in HR Inbox →</button>}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="panel-card">
            <h2 className="panel-title">👎 Answers marked not helpful</h2>
            <p className="panel-sub">Review these to see whether the policy wording or the answer needs improving.</p>
            {data.not_helpful.length === 0 ? (
              <p className="form-hint">No negative ratings yet.</p>
            ) : (
              <ul className="insight-list">
                {data.not_helpful.map((item, i) => (
                  <li key={i}>
                    <span className="insight-question">“{item.question}”</span>
                    <span className="insight-answer">{item.answer}</span>
                    <span className="insight-meta">
                      {item.intent || 'unknown'} · {formatDate(item.asked_at)}
                      {' · '}
                      <button className="link-button" onClick={() => onAskAbout(item.question)}>Try it again →</button>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </section>
  )
}

/* ---------- Ask HR privately (employee) ---------- */

const requestTopics = ['Salary & payroll', 'Personal or medical', 'Workplace concern', 'Leave & attendance', 'Other']

function RequestCard({ item, from, children }) {
  return (
    <div className={`request-card request-${item.status}`}>
      <div className="request-top">
        <span className={`kind-badge kind-${item.kind}`}>
          {item.kind === 'private' ? '🔒 Private' : '✳ Humanly couldn’t answer'}
        </span>
        {item.topic && item.kind === 'private' && <span className="request-topic">{item.topic}</span>}
        <span className={`status-badge status-${item.status}`}>{item.status === 'open' ? 'Waiting for HR' : 'Answered'}</span>
        <span className="request-date">{formatDate(item.created_at)}</span>
      </div>
      {from}
      <p className="request-question">{item.question}</p>
      {item.reply && (
        <div className="request-reply">
          <span className="request-reply-label">HR replied · {formatDate(item.replied_at)}</span>
          <p>{item.reply}</p>
          {item.added_to_knowledge && <span className="taught-badge">✓ Added to Humanly’s knowledge</span>}
        </div>
      )}
      {children}
    </div>
  )
}

function AskHRPage({ onAuthError, onSeen }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [form, setForm] = useState({ topic: requestTopics[0], question: '' })
  const [notice, setNotice] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    try {
      const data = await requestsAPI.mine()
      setItems(data.items)
      if (data.unseen) {
        await requestsAPI.markSeen()
        onSeen()
      }
    } catch (err) {
      if (err.status === 401) onAuthError()
    } finally {
      setLoading(false)
    }
  }, [onAuthError, onSeen])

  useEffect(() => {
    load()
  }, [load])

  async function send(event) {
    event.preventDefault()
    setBusy(true)
    try {
      await requestsAPI.ask(form.topic, form.question.trim())
      setForm({ ...form, question: '' })
      setNotice({ kind: 'success', text: 'Sent to HR ✓ You’ll see their reply here.' })
      await load()
    } catch (err) {
      if (err.status === 401) onAuthError()
      setNotice({ kind: 'error', text: err.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="activity-page">
      <div className="page-heading">
        <span className="welcome-eyebrow">PRIVATE</span>
        <h1>Ask HR</h1>
        <p>For personal questions that a policy can’t answer: your salary, a medical situation, or a concern at work.</p>
      </div>

      <form className="panel-card" onSubmit={send}>
        <div className="privacy-banner">
          <span>🔒</span>
          <p>
            <strong>This goes only to the HR team, never to the AI.</strong> It is tagged with your department so the
            right HR person picks it up.
          </p>
        </div>
        <label className="form-field">
          <span>Topic</span>
          <select value={form.topic} onChange={(e) => setForm({ ...form, topic: e.target.value })}>
            {requestTopics.map((t) => <option key={t}>{t}</option>)}
          </select>
        </label>
        <label className="form-field">
          <span>Your question</span>
          <textarea
            className="form-textarea"
            required
            rows={4}
            value={form.question}
            onChange={(e) => setForm({ ...form, question: e.target.value })}
            placeholder="e.g. My October salary was credited without the travel reimbursement. Who should I contact?"
          />
        </label>
        <div className="panel-actions">
          <button className="return-button" type="submit" disabled={busy || !form.question.trim()}>
            {busy ? 'Sending…' : 'Send to HR →'}
          </button>
        </div>
        {notice && <p className={`notice notice-${notice.kind}`}>{notice.text}</p>}
      </form>

      <div className="activity-list">
        <div className="activity-list-heading">
          <h2>My requests</h2>
          <span>{items.length}</span>
        </div>
        {loading ? (
          <p className="form-hint">Loading…</p>
        ) : items.length === 0 ? (
          <div className="activity-empty">
            <span>✉</span>
            <h3>No requests yet</h3>
            <p>Questions Humanly can’t answer are also sent to HR automatically and appear here.</p>
          </div>
        ) : (
          items.map((item) => <RequestCard key={item.id} item={item} />)
        )}
      </div>
    </section>
  )
}

/* ---------- HR Inbox (HR) ---------- */

function InboxReplyForm({ item, onSent, onAuthError }) {
  const [reply, setReply] = useState('')
  const [teach, setTeach] = useState(item.kind !== 'private')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  async function send(event) {
    event.preventDefault()
    setBusy(true)
    setError('')
    try {
      onSent(await requestsAPI.reply(item.id, reply.trim(), teach && item.kind !== 'private'))
    } catch (err) {
      if (err.status === 401) onAuthError()
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="inbox-reply" onSubmit={send}>
      <textarea
        className="form-textarea"
        rows={3}
        required
        value={reply}
        onChange={(e) => setReply(e.target.value)}
        placeholder="Write your reply to the employee…"
      />
      <div className="inbox-reply-actions">
        {item.kind === 'private' ? (
          <span className="form-hint">🔒 Private: this reply is never added to Humanly’s knowledge.</span>
        ) : (
          <label className="teach-toggle">
            <input type="checkbox" checked={teach} onChange={(e) => setTeach(e.target.checked)} />
            <span>
              <strong>Teach Humanly this answer</strong> so it can answer this question itself next time
            </span>
          </label>
        )}
        <button className="return-button" type="submit" disabled={busy || !reply.trim()}>
          {busy ? 'Sending…' : 'Send reply'}
        </button>
      </div>
      {error && <p className="notice notice-error">{error}</p>}
    </form>
  )
}

function HRInboxPage({ onAuthError }) {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [status, setStatus] = useState('open')
  const [department, setDepartment] = useState('')

  const load = useCallback(async () => {
    try {
      setItems(await requestsAPI.inbox({ department }))
    } catch (err) {
      if (err.status === 401) onAuthError()
    } finally {
      setLoading(false)
    }
  }, [department, onAuthError])

  useEffect(() => {
    load()
  }, [load])

  const counts = {
    open: items.filter((i) => i.status === 'open').length,
    answered: items.filter((i) => i.status === 'answered').length,
    taught: items.filter((i) => i.added_to_knowledge).length,
  }
  const visible = items.filter((i) => !status || i.status === status)

  return (
    <section className="activity-page">
      <div className="page-heading">
        <span className="welcome-eyebrow">HR ADMIN</span>
        <h1>HR Inbox</h1>
        <p>
          Private questions from employees, plus every question Humanly couldn’t answer from a policy. Teach Humanly
          your answer and it will answer that question itself next time.
        </p>
      </div>

      <div className="activity-stats">
        <div className="activity-stat">
          <span>Waiting for a reply</span>
          <strong className={counts.open ? 'stat-warn' : ''}>{counts.open}</strong>
        </div>
        <div className="activity-stat">
          <span>Answered</span>
          <strong>{counts.answered}</strong>
        </div>
        <div className="activity-stat">
          <span>Taught to Humanly</span>
          <strong>{counts.taught}</strong>
        </div>
      </div>

      <div className="directory-toolbar">
        <div className="tab-row">
          {[['open', 'Open'], ['answered', 'Answered'], ['', 'All']].map(([value, label]) => (
            <button key={label} className={`tab-button ${status === value ? 'tab-active' : ''}`} onClick={() => setStatus(value)}>
              {label}
            </button>
          ))}
        </div>
        <select className="directory-filter" value={department} onChange={(e) => setDepartment(e.target.value)}>
          <option value="">All departments</option>
          {departments.map((d) => <option key={d}>{d}</option>)}
        </select>
      </div>

      {loading ? (
        <p className="form-hint">Loading…</p>
      ) : visible.length === 0 ? (
        <div className="activity-empty">
          <span>✓</span>
          <h3>{status === 'open' ? 'Inbox zero' : 'Nothing here'}</h3>
          <p>{status === 'open' ? 'Every request has been answered.' : 'No requests match this filter.'}</p>
        </div>
      ) : (
        visible.map((item) => (
          <RequestCard
            key={item.id}
            item={item}
            from={
              <div className="request-from">
                <div className="avatar">{initials(item.employee.email)}</div>
                <div>
                  <strong>{displayName(item.employee.email)}</strong>
                  <span>{[item.employee.job_title, item.department].filter(Boolean).join(' · ') || item.employee.email}</span>
                </div>
              </div>
            }
          >
            {item.status === 'open' && (
              <InboxReplyForm
                item={item}
                onAuthError={onAuthError}
                onSent={(updated) => setItems((list) => list.map((i) => (i.id === updated.id ? { ...i, ...updated } : i)))}
              />
            )}
          </RequestCard>
        ))
      )}
    </section>
  )
}

/* ---------- Holiday calendar and leave planner ---------- */

const weekdayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

function isoDay(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function parseDay(value) {
  const [y, m, d] = value.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function niceDay(value) {
  return parseDay(value).toLocaleDateString(undefined, { weekday: 'short', day: 'numeric', month: 'short' })
}

// Works out which days are deducted, following Leave Policy sections 3, 5 and 11 (sandwich rule)
function planLeave(from, to, type, holidayByDay) {
  if (!from || !to || to < from) return null
  const days = []
  for (let d = parseDay(from); isoDay(d) <= to; d.setDate(d.getDate() + 1)) {
    const key = isoDay(d)
    const holiday = holidayByDay[key]
    const weekend = d.getDay() === 0 || d.getDay() === 6
    const off = weekend || holiday?.kind === 'fixed' // optional holidays are working days
    days.push({ key, off, reason: holiday?.kind === 'fixed' ? holiday.name : weekend ? 'Weekend' : null })
  }
  const working = days.filter((d) => !d.off)
  if (!working.length) return { days, working: 0, counted: 0, sandwiched: [], status: {}, warnings: ['There are no working days in these dates.'] }

  const first = working[0].key
  const last = working[working.length - 1].key
  const sandwichApplies = type === 'casual'
  const sandwiched = sandwichApplies ? days.filter((d) => d.off && d.key > first && d.key < last) : []
  const status = {}
  days.forEach((d) => {
    if (!d.off) status[d.key] = 'leave'
    else if (sandwiched.includes(d)) status[d.key] = 'sandwich'
    else status[d.key] = 'free'
  })

  const warnings = []
  if (type === 'casual' && working.length > 3) warnings.push('Casual leave can’t be more than 3 consecutive days (Leave Policy, section 3).')
  if (type === 'earned') {
    if (working.length < 2) warnings.push('Earned leave must be at least 2 days per application (section 5).')
    const notice = new Date()
    notice.setDate(notice.getDate() + 14)
    if (from < isoDay(notice)) warnings.push('Earned leave must be applied for at least 14 days in advance (section 5).')
  }
  if (type === 'sick' && working.length >= 3) warnings.push('3 or more days of sick leave need a medical certificate (section 4).')

  return { days, working: working.length, counted: working.length + sandwiched.length, sandwiched, status, warnings }
}

const plannerExamples = [
  { label: 'Fri + Mon (weekend between)', type: 'casual', from: '2026-12-11', to: '2026-12-14' },
  { label: 'Around Christmas', type: 'casual', from: '2026-12-24', to: '2026-12-28' },
  { label: 'Same dates, earned leave', type: 'earned', from: '2026-12-24', to: '2026-12-28' },
]

function CalendarPage({ isHR, onAuthError }) {
  const today = isoDay(new Date())
  const [holidays, setHolidays] = useState([])
  const [month, setMonth] = useState(() => {
    const now = new Date()
    return new Date(now.getFullYear(), now.getMonth(), 1)
  })
  const [plan, setPlan] = useState({ type: 'casual', from: '', to: '' })
  const [newHoliday, setNewHoliday] = useState({ day: '', name: '', kind: 'fixed' })
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    try {
      setHolidays(await holidaysAPI.list())
    } catch (err) {
      if (err.status === 401) onAuthError()
      setError(err.message)
    }
  }, [onAuthError])

  useEffect(() => {
    load()
  }, [load])

  const holidayByDay = Object.fromEntries(holidays.map((h) => [h.day, h]))
  const result = planLeave(plan.from, plan.to, plan.type, holidayByDay)

  function setPlanAndShow(next) {
    setPlan(next)
    if (next.from) {
      const d = parseDay(next.from)
      setMonth(new Date(d.getFullYear(), d.getMonth(), 1))
    }
  }

  // Monday-first grid for the shown month
  const cells = []
  const lead = (month.getDay() + 6) % 7
  for (let i = 0; i < lead; i += 1) cells.push(null)
  const daysInMonth = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate()
  for (let d = 1; d <= daysInMonth; d += 1) cells.push(isoDay(new Date(month.getFullYear(), month.getMonth(), d)))

  const upcoming = holidays.filter((h) => h.day >= today).slice(0, 6)

  async function addHoliday(event) {
    event.preventDefault()
    try {
      await holidaysAPI.add(newHoliday.day, newHoliday.name.trim(), newHoliday.kind)
      setNewHoliday({ day: '', name: '', kind: 'fixed' })
      setError('')
      await load()
    } catch (err) {
      if (err.status === 401) onAuthError()
      setError(err.message)
    }
  }

  async function removeHoliday(h) {
    if (!window.confirm(`Remove ${h.name} (${niceDay(h.day)}) from the calendar?`)) return
    try {
      await holidaysAPI.remove(h.id)
      await load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <section className="activity-page calendar-page">
      <div className="page-heading">
        <span className="welcome-eyebrow">HOLIDAYS & LEAVE</span>
        <h1>Holiday calendar</h1>
        <p>Company holidays for the year, and a leave planner that shows exactly how many days will be deducted, including the sandwich rule.</p>
      </div>

      {error && <p className="notice notice-error">{error}</p>}

      <div className="calendar-layout">
        <div className="panel-card calendar-card">
          <div className="calendar-head">
            <button className="ghost-button" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))} aria-label="Previous month">‹</button>
            <h2>{month.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}</h2>
            <button className="ghost-button" onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))} aria-label="Next month">›</button>
          </div>
          <div className="calendar-grid">
            {weekdayNames.map((w) => <span key={w} className="calendar-weekday">{w}</span>)}
            {cells.map((key, i) => {
              if (!key) return <span key={`blank-${i}`} />
              const h = holidayByDay[key]
              const dow = parseDay(key).getDay()
              const classes = [
                'calendar-day',
                (dow === 0 || dow === 6) && 'calendar-weekend',
                h && `calendar-${h.kind}`,
                key === today && 'calendar-today',
                result?.status[key] && `plan-${result.status[key]}`,
              ].filter(Boolean).join(' ')
              return (
                <div key={key} className={classes} title={h ? `${h.name} (${h.kind})` : ''}>
                  <span className="calendar-num">{parseDay(key).getDate()}</span>
                  {h && <span className="calendar-label">{h.name}</span>}
                </div>
              )
            })}
          </div>
          <div className="calendar-legend">
            <span><i className="dot dot-fixed" /> Fixed holiday</span>
            <span><i className="dot dot-optional" /> Optional holiday</span>
            <span><i className="dot dot-leave" /> Leave day</span>
            <span><i className="dot dot-sandwich" /> Sandwiched (counted)</span>
          </div>
        </div>

        <div className="calendar-side">
          <div className="panel-card">
            <h2 className="panel-title">Plan your leave</h2>
            <p className="panel-sub">Pick dates to see how many days are deducted.</p>
            <label className="form-field">
              <span>Leave type</span>
              <select value={plan.type} onChange={(e) => setPlan({ ...plan, type: e.target.value })}>
                <option value="casual">Casual leave</option>
                <option value="earned">Earned leave</option>
                <option value="sick">Sick leave</option>
              </select>
            </label>
            <div className="form-row">
              <label className="form-field">
                <span>From</span>
                <input type="date" value={plan.from} onChange={(e) => setPlanAndShow({ ...plan, from: e.target.value, to: plan.to && plan.to >= e.target.value ? plan.to : e.target.value })} />
              </label>
              <label className="form-field">
                <span>To</span>
                <input type="date" value={plan.to} min={plan.from} onChange={(e) => setPlan({ ...plan, to: e.target.value })} />
              </label>
            </div>
            <div className="example-row">
              <span>Try:</span>
              {plannerExamples.map((ex) => (
                <button key={ex.label} className="chip-button" onClick={() => setPlanAndShow({ type: ex.type, from: ex.from, to: ex.to })}>
                  {ex.label}
                </button>
              ))}
            </div>

            {result && (
              <div className="plan-result">
                <div className="plan-total">
                  <strong>{result.counted}</strong>
                  <span>day{result.counted === 1 ? '' : 's'} of {plan.type} leave deducted</span>
                </div>
                <p className="plan-line">{result.working} working day{result.working === 1 ? '' : 's'} off work</p>
                {result.sandwiched.length > 0 && (
                  <p className="plan-line plan-sandwich">
                    🥪 Sandwich rule: +{result.sandwiched.length} ({result.sandwiched.map((d) => `${niceDay(d.key)}${d.reason !== 'Weekend' ? ` – ${d.reason}` : ''}`).join(', ')})
                  </p>
                )}
                {plan.type !== 'casual' && result.days.some((d) => d.off) && (
                  <p className="plan-line">Weekends and fixed holidays in between are not counted for {plan.type} leave.</p>
                )}
                {result.warnings.map((w) => <p key={w} className="plan-warning">⚠ {w}</p>)}
              </div>
            )}
          </div>

          <div className="panel-card">
            <h2 className="panel-title">Upcoming holidays</h2>
            {upcoming.length === 0 ? (
              <p className="form-hint">No more holidays this year.</p>
            ) : (
              <ul className="holiday-list">
                {upcoming.map((h) => (
                  <li key={h.id}>
                    <span className={`dot dot-${h.kind}`} />
                    <span className="holiday-name">{h.name}</span>
                    <span className="holiday-date">{niceDay(h.day)}</span>
                    {isHR && <button className="holiday-remove" onClick={() => removeHoliday(h)} aria-label={`Remove ${h.name}`}>×</button>}
                  </li>
                ))}
              </ul>
            )}
          </div>

          {isHR && (
            <form className="panel-card" onSubmit={addHoliday}>
              <h2 className="panel-title">Add a holiday</h2>
              <label className="form-field">
                <span>Name</span>
                <input required value={newHoliday.name} onChange={(e) => setNewHoliday({ ...newHoliday, name: e.target.value })} placeholder="e.g. Kannada Rajyotsava" />
              </label>
              <div className="form-row">
                <label className="form-field">
                  <span>Date</span>
                  <input required type="date" value={newHoliday.day} onChange={(e) => setNewHoliday({ ...newHoliday, day: e.target.value })} />
                </label>
                <label className="form-field">
                  <span>Type</span>
                  <select value={newHoliday.kind} onChange={(e) => setNewHoliday({ ...newHoliday, kind: e.target.value })}>
                    <option value="fixed">Fixed</option>
                    <option value="optional">Optional</option>
                  </select>
                </label>
              </div>
              <button className="return-button" type="submit">Add holiday</button>
            </form>
          )}
        </div>
      </div>
    </section>
  )
}

/* ---------- HR: manage policy documents ---------- */

function ManagePoliciesPage({ onAuthError }) {
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  // Shown right where the action happened: { where: 'upload' | <document id>, kind, text }
  const [notice, setNotice] = useState(null)
  const [upload, setUpload] = useState({ title: '', version: '', file: null })
  const [replacing, setReplacing] = useState(null) // { id, version, file }
  const fileInputRef = useRef(null)

  const load = useCallback(async () => {
    try {
      setDocuments(await documentsAPI.getAll())
    } catch (err) {
      if (err.status === 401) onAuthError()
      setNotice({ where: 'upload', kind: 'error', text: err.message })
    } finally {
      setLoading(false)
    }
  }, [onAuthError])

  useEffect(() => {
    load()
  }, [load])

  async function run(where, working, done, action) {
    setBusy(true)
    setNotice({ where, kind: 'info', text: working })
    try {
      const result = await action()
      // an action can move the message, e.g. a replace creates a new card id
      setNotice({ where: result?.where ?? where, kind: 'success', text: done })
      await load()
    } catch (err) {
      if (err.status === 401) onAuthError()
      setNotice({ where, kind: 'error', text: err.message })
    } finally {
      setBusy(false)
    }
  }

  function Notice({ where }) {
    if (!notice || notice.where !== where) return null
    return <p className={`notice notice-${notice.kind}`} role="status">{notice.text}</p>
  }

  function handleUpload(event) {
    event.preventDefault()
    if (!upload.file) return
    const title = upload.title.trim()
    run('upload', 'Uploading and indexing… (the first upload can take a minute)', `"${title}" uploaded ✓`, async () => {
      await documentsAPI.upload({ ...upload, title, version: upload.version.trim() })
      setUpload({ title: '', version: '', file: null })
      if (fileInputRef.current) fileInputRef.current.value = ''
    })
  }

  function handleReplace(event, doc) {
    event.preventDefault()
    if (!replacing?.file) return
    const version = replacing.version.trim()
    run(doc.id, `Uploading version ${version}…`, `Version ${version} is now current ✓`, async () => {
      const created = await documentsAPI.replace(replacing.id, version, replacing.file)
      setReplacing(null)
      return { where: created.id } // the new version has a new id: show the message on its card
    })
  }

  function handleDelete(doc) {
    if (!window.confirm(`Delete "${doc.title}" and all its versions? Employees will no longer get answers from it.`)) return
    run('upload', 'Deleting…', `"${doc.title}" deleted ✓`, () => documentsAPI.delete(doc.id))
  }

  // One card per policy: the current version, with older versions underneath
  const families = Object.values(
    documents.reduce((groups, doc) => {
      const key = doc.family_id ?? doc.id
      groups[key] = groups[key] || { current: null, archived: [] }
      if (doc.status === 'current') groups[key].current = doc
      else groups[key].archived.push(doc)
      return groups
    }, {}),
  ).filter((family) => family.current)

  return (
    <section className="activity-page">
      <div className="page-heading">
        <span className="welcome-eyebrow">HR ADMIN</span>
        <h1>Manage policies</h1>
        <p>Upload PDF or Word policies. To update a policy, use Replace: the old version is kept so employees can ask what changed.</p>
      </div>

      <form className="panel-card upload-form" onSubmit={handleUpload}>
        <h2 className="panel-title">Upload a new policy</h2>
        <div className="form-row">
          <label className="form-field">
            <span>Policy title</span>
            <input required value={upload.title} onChange={(e) => setUpload({ ...upload, title: e.target.value })} placeholder="e.g. Leave Policy" />
          </label>
          <label className="form-field">
            <span>Version</span>
            <input required value={upload.version} onChange={(e) => setUpload({ ...upload, version: e.target.value })} placeholder="e.g. 2026" />
          </label>
          <label className="form-field">
            <span>File (PDF or DOCX)</span>
            <input ref={fileInputRef} required type="file" accept=".pdf,.docx" onChange={(e) => setUpload({ ...upload, file: e.target.files[0] || null })} />
          </label>
        </div>
        <div className="panel-actions">
          <button className="return-button" type="submit" disabled={busy}>Upload policy</button>
        </div>
        <Notice where="upload" />
      </form>

      <div className="activity-list">
        <div className="activity-list-heading">
          <h2>Indexed policies</h2>
          <span>{families.length}</span>
        </div>

        {loading ? (
          <p className="form-hint">Loading…</p>
        ) : families.length === 0 ? (
          <div className="activity-empty">
            <span>▤</span>
            <h3>No policies yet</h3>
            <p>Upload your first policy above.</p>
          </div>
        ) : (
          families.map(({ current, archived }) => (
            <div className="doc-card" key={current.id}>
              <div className="activity-item">
                <div className="activity-item-icon">▤</div>
                <div className="activity-item-copy">
                  <h3>{current.title}</h3>
                  <p>
                    Current version {current.version} · {current.chunk_count} sections · uploaded {formatDate(current.uploaded_at)}
                  </p>
                  {archived.length > 0 && (
                    <p className="doc-archived">
                      Older version{archived.length > 1 ? 's' : ''} kept for comparison:{' '}
                      {archived.map((doc) => `v${doc.version}`).join(', ')}
                    </p>
                  )}
                </div>
                <button
                  className="activity-open-button"
                  disabled={busy}
                  onClick={() => { setReplacing({ id: current.id, version: '', file: null }); setNotice(null) }}
                >
                  Replace
                </button>
                <button className="activity-open-button danger-button" disabled={busy} onClick={() => handleDelete(current)}>
                  Delete
                </button>
              </div>

              {replacing?.id === current.id && (
                <form className="replace-form" onSubmit={(event) => handleReplace(event, current)}>
                  <span className="replace-label">Upload a newer version of {current.title}:</span>
                  <input required value={replacing.version} onChange={(e) => setReplacing({ ...replacing, version: e.target.value })} placeholder="New version, e.g. 2027" />
                  <input required type="file" accept=".pdf,.docx" onChange={(e) => setReplacing({ ...replacing, file: e.target.files[0] || null })} />
                  <button className="return-button" type="submit" disabled={busy}>Upload version</button>
                  <button className="ghost-button" type="button" onClick={() => { setReplacing(null); setNotice(null) }}>Cancel</button>
                </form>
              )}
              <Notice where={current.id} />
            </div>
          ))
        )}
      </div>
    </section>
  )
}

/* ---------- Main app ---------- */

function App() {
  const [user, setUser] = useState(null)
  const [checkingSession, setCheckingSession] = useState(true)
  const [backendOnline, setBackendOnline] = useState(true)

  const [message, setMessage] = useState('')
  const [activePage, setActivePage] = useState('New chat')
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [conversations, setConversations] = useState([])
  const [activeConversationId, setActiveConversationId] = useState(null)
  const [messages, setMessages] = useState([])
  const [liveSteps, setLiveSteps] = useState([])
  const [policySearch, setPolicySearch] = useState('')
  const [isTyping, setIsTyping] = useState(false)
  const [helpOpen, setHelpOpen] = useState(false)
  const [unseenReplies, setUnseenReplies] = useState(0)
  const messagesEndRef = useRef(null)

  const activeConversation = conversations.find(
    (conversation) => conversation.id === activeConversationId,
  )
  const isHR = user?.role === 'hr_admin'

  const filteredPolicies = policyCategories.filter((policy) => {
    const query = policySearch.toLowerCase().trim()
    return (
      policy.title.toLowerCase().includes(query) ||
      policy.description.toLowerCase().includes(query)
    )
  })

  const logout = useCallback(() => {
    authAPI.logout()
    setUser(null)
    setConversations([])
    setMessages([])
    setActiveConversationId(null)
    setActivePage('New chat')
  }, [])

  const loadConversations = useCallback(async () => {
    try {
      setConversations(await chatAPI.getConversations())
    } catch (err) {
      if (err.status === 401) logout()
    }
  }, [logout])

  // On start: is the backend up, and is there a saved login?
  useEffect(() => {
    systemAPI.health().then(() => setBackendOnline(true)).catch(() => setBackendOnline(false))
    if (!authAPI.hasToken()) {
      setCheckingSession(false)
      return
    }
    authAPI
      .getProfile()
      .then(setUser)
      .catch(() => authAPI.logout())
      .finally(() => setCheckingSession(false))
  }, [])

  useEffect(() => {
    if (user) loadConversations()
  }, [user, loadConversations])

  // Employees: how many HR replies they haven't read yet (badge on "Ask HR")
  const checkReplies = useCallback(() => {
    if (!user || user.role === 'hr_admin') return
    requestsAPI.mine().then((data) => setUnseenReplies(data.unseen)).catch(() => {})
  }, [user])

  useEffect(() => {
    checkReplies()
  }, [checkReplies, activePage])

  const clearReplies = useCallback(() => setUnseenReplies(0), [])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, liveSteps, isTyping])

  function startNewChat() {
    setActiveConversationId(null)
    setMessages([])
    setMessage('')
    setActivePage('New chat')
    setSidebarOpen(false)
  }

  async function openConversation(conversationId) {
    setActiveConversationId(conversationId)
    setActivePage('New chat')
    setMessage('')
    setSidebarOpen(false)
    try {
      const conversation = await chatAPI.getConversation(conversationId)
      setMessages(
        conversation.messages.map((item, index) => ({
          id: `${conversationId}-${index}`,
          role: item.sender,
          content: item.content,
          citations: item.citations || [],
          messageId: item.sender === 'assistant' ? item.id : null,
          feedback: item.feedback ?? null,
        })),
      )
    } catch (err) {
      if (err.status === 401) logout()
    }
  }

  async function handleSubmit(event) {
    event.preventDefault()

    const question = message.trim()
    if (!question || isTyping) return

    setMessages((previous) => [...previous, { id: crypto.randomUUID(), role: 'user', content: question }])
    setMessage('')
    setActivePage('New chat')
    setIsTyping(true)
    setLiveSteps([])

    try {
      const result = await chatAPI.streamMessage(question, activeConversationId, (step) =>
        setLiveSteps((previous) => [...previous, step]),
      )
      setMessages((previous) => [
        ...previous,
        {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: result.answer,
          citations: result.citations,
          trace: result.trace,
          messageId: result.message_id,
          feedback: null,
        },
      ])
      if (!activeConversationId) {
        setActiveConversationId(result.conversation_id)
        loadConversations()
      }
    } catch (err) {
      if (err.status === 401) {
        logout()
        return
      }
      setMessages((previous) => [
        ...previous,
        { id: crypto.randomUUID(), role: 'assistant', content: `Sorry, something went wrong: ${err.message}. Please try again.`, error: true },
      ])
    } finally {
      setIsTyping(false)
      setLiveSteps([])
    }
  }

  function selectSuggestion(prompt) {
    setActivePage('New chat')
    setMessage(prompt)
    setSidebarOpen(false)
  }

  async function deleteConversation(conversationId) {
    try {
      await chatAPI.deleteConversation(conversationId)
    } catch (err) {
      if (err.status === 401) return logout()
    }
    setConversations((previous) => previous.filter((conversation) => conversation.id !== conversationId))
    if (activeConversationId === conversationId) startNewChat()
  }

  function setFeedback(id, value) {
    setMessages((previous) => previous.map((item) => (item.id === id ? { ...item, feedback: value } : item)))
  }

  function goTo(page) {
    setActivePage(page)
    setSidebarOpen(false)
  }

  if (checkingSession) {
    return <div className="auth-shell"><p className="form-hint">Loading…</p></div>
  }

  if (!user) {
    return <AuthScreen backendOnline={backendOnline} onLoggedIn={setUser} />
  }

  const breadcrumb =
    activePage === 'New chat' && messages.length > 0
      ? activeConversation?.title || shortTitle(messages[0]?.content || 'Conversation')
      : activePage

  function renderComposer() {
    return (
      <div className="composer-wrapper">
        <form className="chat-composer" onSubmit={handleSubmit}>
          <textarea
            value={message}
            onChange={(event) => setMessage(event.target.value)}
            placeholder="Ask anything about your HR policies..."
            aria-label="Ask a question about HR policies"
            rows={2}
            onKeyDown={(event) => {
              if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                event.preventDefault()
                event.currentTarget.form?.requestSubmit()
              }
            }}
          />
          <div className="composer-bottom">
            <span className="composer-hint">
              <span className="hint-icon">↵</span>
              Enter to send · Shift + Enter for a new line
            </span>

            <button className="send-button" type="submit" disabled={!message.trim() || isTyping} aria-label="Send message">
              <span>Send</span>
              <span className="send-arrow">↑</span>
            </button>
          </div>
        </form>

        <p className="disclaimer">
          Answers come only from your company's uploaded HR policies. Check the cited source for important decisions.
        </p>
      </div>
    )
  }

  return (
    <div className="app-shell">
      {sidebarOpen && (
        <button className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setSidebarOpen(false)} />
      )}

      <aside className={`sidebar ${sidebarOpen ? 'sidebar-open' : ''}`}>
        <div className="sidebar-brand">
          <div className="brand-mark">H</div>
          <div className="brand-copy">
            <span className="brand-name">HUMANLY</span>
            <span className="brand-caption">HR INTELLIGENCE</span>
          </div>
          <button className="icon-button sidebar-close" onClick={() => setSidebarOpen(false)} aria-label="Close sidebar">
            ×
          </button>
        </div>

        <button className="new-chat-button" onClick={startNewChat}>
          <span className="new-chat-plus">＋</span>
          <span>New conversation</span>
          <span className="new-chat-shortcut">↵</span>
        </button>

        <div className="sidebar-section">
          <p className="sidebar-label">WORKSPACE</p>

          <button className={`nav-item ${activePage === 'New chat' ? 'nav-active' : ''}`} onClick={() => goTo('New chat')}>
            <span className="nav-icon">✳</span>
            <span>AI Assistant</span>
            <span className="active-indicator" />
          </button>

          <button className={`nav-item ${activePage === 'Policy library' ? 'nav-active' : ''}`} onClick={() => goTo('Policy library')}>
            <span className="nav-icon">▤</span>
            <span>Policy library</span>
          </button>

          <button className={`nav-item ${activePage === 'My activity' ? 'nav-active' : ''}`} onClick={() => goTo('My activity')}>
            <span className="nav-icon">◷</span>
            <span>My activity</span>
          </button>

          <button className={`nav-item ${activePage === 'Holiday calendar' ? 'nav-active' : ''}`} onClick={() => goTo('Holiday calendar')}>
            <span className="nav-icon">▦</span>
            <span>Holiday calendar</span>
          </button>

          {!isHR && (
            <button className={`nav-item ${activePage === 'Ask HR' ? 'nav-active' : ''}`} onClick={() => goTo('Ask HR')}>
              <span className="nav-icon">✉</span>
              <span>Ask HR</span>
              {unseenReplies > 0 && <span className="nav-badge">{unseenReplies}</span>}
            </button>
          )}

          {isHR && (
            <button className={`nav-item ${activePage === 'Manage policies' ? 'nav-active' : ''}`} onClick={() => goTo('Manage policies')}>
              <span className="nav-icon">⇪</span>
              <span>Manage policies</span>
            </button>
          )}

          {isHR && (
            <button className={`nav-item ${activePage === 'HR Inbox' ? 'nav-active' : ''}`} onClick={() => goTo('HR Inbox')}>
              <span className="nav-icon">✉</span>
              <span>HR Inbox</span>
            </button>
          )}

          {isHR && (
            <button className={`nav-item ${activePage === 'Employees' ? 'nav-active' : ''}`} onClick={() => goTo('Employees')}>
              <span className="nav-icon">☺</span>
              <span>Employees</span>
            </button>
          )}

          {isHR && (
            <button className={`nav-item ${activePage === 'Insights' ? 'nav-active' : ''}`} onClick={() => goTo('Insights')}>
              <span className="nav-icon">▥</span>
              <span>Insights</span>
            </button>
          )}
        </div>

        <div className="sidebar-section conversation-section">
          <div className="conversation-heading">
            <p className="sidebar-label">RECENT CONVERSATIONS</p>
            <span className="history-count">{conversations.length}</span>
          </div>

          {conversations.length === 0 ? (
            <div className="empty-history">
              <span className="history-symbol">◷</span>
              <p>Your conversations will appear here.</p>
            </div>
          ) : (
            <div className="conversation-list">
              {conversations.slice(0, 8).map((conversation) => (
                <div
                  className={`history-item ${activeConversationId === conversation.id ? 'history-item-active' : ''}`}
                  key={conversation.id}
                >
                  <button className="history-open" onClick={() => openConversation(conversation.id)} title={conversation.title}>
                    <span className="history-symbol">◷</span>
                    <span>{shortTitle(conversation.title)}</span>
                  </button>
                  <button
                    className="history-delete"
                    onClick={() => deleteConversation(conversation.id)}
                    aria-label={`Delete ${conversation.title}`}
                    title="Delete conversation"
                  >
                    ×
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="sidebar-bottom">
          <div className="privacy-card">
            <div className="privacy-icon">✦</div>
            <div>
              <p className="privacy-title">Your HR companion</p>
              <p className="privacy-description">Clear answers. Better decisions.</p>
            </div>
          </div>

          <button className="sidebar-footer footer-button" onClick={() => goTo('My profile')} title="Open your profile">
            <div className="avatar">{initials(user.email)}</div>
            <div className="profile-copy">
              <span className="profile-name">{displayName(user.email)}</span>
              <span className="profile-role">{isHR ? 'HR admin' : user.department || 'Employee workspace'}</span>
            </div>
            <span className="profile-menu">···</span>
          </button>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div className="topbar-left">
            <button className="icon-button mobile-menu" onClick={() => setSidebarOpen(true)} aria-label="Open navigation">
              ☰
            </button>
            <div className="breadcrumb">
              <span>Workspace</span>
              <span className="breadcrumb-divider">/</span>
              <span className="breadcrumb-current">{breadcrumb}</span>
            </div>
          </div>

          <div className="topbar-right">
            <div className="system-status">
              <span className={`status-dot ${backendOnline ? '' : 'status-dot-offline'}`} />
              <span>{backendOnline ? 'Connected' : 'Backend offline'}</span>
            </div>
            <button className="help-button" aria-label="Help" onClick={() => setHelpOpen((previous) => !previous)}>
              ?
            </button>
          </div>
        </header>

        {helpOpen && (
          <div className="help-panel" role="status">
            <strong>Welcome to HUMANLY</strong>
            <p>
              Ask about leave, travel claims, eligibility or what changed in a policy. Every answer
              comes from your company's uploaded policies, with the source shown underneath.
            </p>
            <button onClick={() => setHelpOpen(false)}>Got it</button>
          </div>
        )}

        {activePage === 'New chat' ? (
          messages.length === 0 && !isTyping ? (
            <section className="welcome-area">
              <div className="welcome-content">
                <div className="welcome-eyebrow">
                  <span className="eyebrow-sparkle">✳</span>
                  YOUR PERSONAL HR ASSISTANT
                </div>

                <h1>
                  Work questions,
                  <br />
                  <span>meet clear answers.</span>
                </h1>

                <p className="welcome-description">
                  From leave policies to employee benefits, find the information
                  you need to navigate your workplace with confidence.
                </p>

                <div className="trust-line">
                  <span className="trust-check">✓</span>
                  Policy-focused answers
                  <span className="trust-separator">·</span>
                  Simple explanations
                  <span className="trust-separator">·</span>
                  Less guesswork
                </div>

                <div className="suggestions-heading">
                  <div>
                    <h2>What can I help you with?</h2>
                    <p>Choose a topic to get started.</p>
                  </div>
                  <span className="suggestion-count">04 TOPICS</span>
                </div>

                <div className="suggestion-grid">
                  {suggestions.map((suggestion, index) => (
                    <button className="suggestion-card" key={suggestion.title} onClick={() => selectSuggestion(suggestion.prompt)}>
                      <div className="suggestion-card-top">
                        <span className={`suggestion-icon suggestion-icon-${index}`}>{suggestion.icon}</span>
                        <span className="suggestion-arrow">↗</span>
                      </div>
                      <h3>{suggestion.title}</h3>
                      <p>{suggestion.description}</p>
                    </button>
                  ))}
                </div>

                {renderComposer()}
              </div>
            </section>
          ) : (
            <section className="chat-page">
              <div className="chat-messages">
                {messages.map((item) => (
                  <article className={`message-row message-${item.role}`} key={item.id}>
                    <div className="message-avatar">{item.role === 'user' ? initials(user.email) : 'H'}</div>
                    <div className={`message-body ${item.error ? 'message-error' : ''}`}>
                      <span className="message-author">{item.role === 'user' ? 'You' : 'HUMANLY'}</span>
                      <p>{item.content}</p>
                      {item.role === 'assistant' && item.content?.startsWith("This isn't covered") && (
                        <p className="sent-to-hr">
                          📨 Sent to HR automatically.{' '}
                          {!isHR && <button className="link-button" onClick={() => goTo('Ask HR')}>You’ll see their reply in Ask HR →</button>}
                        </p>
                      )}
                      {item.role === 'assistant' && <Citations citations={item.citations} />}
                      {item.role === 'assistant' && <AgentTrace steps={item.trace} />}
                      {item.role === 'assistant' && !item.error && (
                        <Feedback messageId={item.messageId} value={item.feedback} onChange={(value) => setFeedback(item.id, value)} />
                      )}
                    </div>
                  </article>
                ))}

                {isTyping && (
                  <div className="message-row message-assistant">
                    <div className="message-avatar">H</div>
                    <div className="message-body">
                      <span className="message-author">HUMANLY</span>
                      <p className="typing-indicator">
                        <span /><span /><span /> Thinking…
                      </p>
                      <AgentTrace steps={liveSteps} live />
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>

              {renderComposer()}
            </section>
          )
        ) : activePage === 'Policy library' ? (
          <section className="library-page">
            <div className="page-heading">
              <span className="welcome-eyebrow">HR KNOWLEDGE BASE</span>
              <h1>Policy library</h1>
              <p>Pick a topic to get a summary straight from the current policy.</p>
            </div>

            <label className="library-search">
              <span>⌕</span>
              <input
                value={policySearch}
                onChange={(event) => setPolicySearch(event.target.value)}
                placeholder="Search policy categories..."
                aria-label="Search policy categories"
              />
            </label>

            <div className="policy-grid">
              {filteredPolicies.map((policy) => (
                <button className="policy-card" key={policy.title} onClick={() => selectSuggestion(policy.prompt)}>
                  <span className="policy-card-icon">{policy.icon}</span>
                  <h2>{policy.title}</h2>
                  <p>{policy.description}</p>
                  <span className="policy-card-link">Ask HUMANLY →</span>
                </button>
              ))}

              {filteredPolicies.length === 0 && (
                <div className="library-empty">
                  <h2>No categories found</h2>
                  <p>Try a different search term.</p>
                </div>
              )}
            </div>

            <p className="library-note">
              {isHR
                ? 'To add or update policy documents, open Manage policies.'
                : 'Answers come from the policy documents uploaded by HR.'}
            </p>
          </section>
        ) : activePage === 'Manage policies' && isHR ? (
          <ManagePoliciesPage onAuthError={logout} />
        ) : activePage === 'Employees' && isHR ? (
          <EmployeesPage onAuthError={logout} />
        ) : activePage === 'Insights' && isHR ? (
          <InsightsPage onAuthError={logout} onAskAbout={(question) => { startNewChat(); setMessage(question) }} onOpenInbox={() => goTo('HR Inbox')} />
        ) : activePage === 'HR Inbox' && isHR ? (
          <HRInboxPage onAuthError={logout} />
        ) : activePage === 'Ask HR' && !isHR ? (
          <AskHRPage onAuthError={logout} onSeen={clearReplies} />
        ) : activePage === 'Holiday calendar' ? (
          <CalendarPage isHR={isHR} onAuthError={logout} />
        ) : activePage === 'My profile' ? (
          <ProfilePage user={user} onSaved={setUser} onLogout={logout} />
        ) : (
          <section className="activity-page">
            <div className="page-heading">
              <span className="welcome-eyebrow">YOUR WORKSPACE</span>
              <h1>My activity</h1>
              <p>All your conversations, saved to your account.</p>
            </div>

            <div className="activity-stats">
              <div className="activity-stat">
                <span>Total conversations</span>
                <strong>{conversations.length}</strong>
              </div>
              <div className="activity-stat">
                <span>Months of service</span>
                <strong>{monthsOfService(user.join_date) ?? '–'}</strong>
              </div>
              <div className="activity-stat">
                <span>Department · City</span>
                <strong className="stat-small">{[user.department, user.city].filter(Boolean).join(' · ') || '–'}</strong>
              </div>
            </div>

            <div className="activity-list">
              <div className="activity-list-heading">
                <h2>Recent conversations</h2>
                <span>{conversations.length}</span>
              </div>

              {conversations.length === 0 ? (
                <div className="activity-empty">
                  <span>◷</span>
                  <h3>No activity yet</h3>
                  <p>Your conversations will appear here after you ask a question.</p>
                  <button className="return-button" onClick={startNewChat}>Start a conversation →</button>
                </div>
              ) : (
                conversations.map((conversation) => (
                  <div className="activity-item" key={conversation.id}>
                    <div className="activity-item-icon">✳</div>
                    <div className="activity-item-copy">
                      <h3>{conversation.title}</h3>
                      <p>{formatDate(conversation.created_at)}</p>
                    </div>
                    <button className="activity-open-button" onClick={() => openConversation(conversation.id)}>
                      Open →
                    </button>
                  </div>
                ))
              )}
            </div>
          </section>
        )}
      </main>
    </div>
  )
}

export default App
