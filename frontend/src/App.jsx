import { useCallback, useEffect, useRef, useState } from 'react'
import './App.css'
import { authAPI, chatAPI, documentsAPI, systemAPI } from './services/api'

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
  const [form, setForm] = useState({ email: '', password: '', join_date: '', grade: '', city: '' })
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
          grade: form.grade.trim() || null,
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
            : 'Your joining date, grade and city let HUMANLY answer eligibility and allowance questions for you.'}
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
          <div className="form-row">
            <label className="form-field">
              <span>Joining date</span>
              <input type="date" value={form.join_date} onChange={(e) => update('join_date', e.target.value)} />
            </label>
            <label className="form-field">
              <span>Grade</span>
              <input value={form.grade} onChange={(e) => update('grade', e.target.value)} placeholder="e.g. L3" />
            </label>
            <label className="form-field">
              <span>City</span>
              <input value={form.city} onChange={(e) => update('city', e.target.value)} placeholder="e.g. Bengaluru" />
            </label>
          </div>
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

/* ---------- Profile page ---------- */

function ProfilePage({ user, onSaved, onLogout }) {
  const [form, setForm] = useState({
    join_date: user.join_date || '',
    grade: user.grade || '',
    city: user.city || '',
  })
  const [status, setStatus] = useState('')

  async function save(event) {
    event.preventDefault()
    setStatus('Saving…')
    try {
      const updated = await authAPI.updateProfile({
        join_date: form.join_date || null,
        grade: form.grade.trim() || null,
        city: form.city.trim() || null,
      })
      onSaved(updated)
      setStatus('Saved ✓')
    } catch (err) {
      setStatus(err.message)
    }
  }

  const months = monthsOfService(form.join_date)

  return (
    <section className="activity-page">
      <div className="page-heading">
        <span className="welcome-eyebrow">YOUR ACCOUNT</span>
        <h1>My profile</h1>
        <p>HUMANLY uses these details to answer eligibility and allowance questions for you.</p>
      </div>

      <form className="panel-card" onSubmit={save}>
        <div className="form-row">
          <label className="form-field">
            <span>Email</span>
            <input value={user.email} disabled />
          </label>
          <label className="form-field">
            <span>Role</span>
            <input value={user.role === 'hr_admin' ? 'HR admin' : 'Employee'} disabled />
          </label>
        </div>
        <div className="form-row">
          <label className="form-field">
            <span>Joining date</span>
            <input type="date" value={form.join_date} onChange={(e) => setForm({ ...form, join_date: e.target.value })} />
          </label>
          <label className="form-field">
            <span>Grade</span>
            <input value={form.grade} onChange={(e) => setForm({ ...form, grade: e.target.value })} placeholder="e.g. L3" />
          </label>
          <label className="form-field">
            <span>City</span>
            <input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} placeholder="e.g. Bengaluru" />
          </label>
        </div>
        {months !== null && <p className="form-hint">That's {months} full month(s) of service.</p>}

        <div className="panel-actions">
          <button className="return-button" type="submit">Save profile</button>
          <span className="form-hint">{status}</span>
          <button className="ghost-button" type="button" onClick={onLogout}>Sign out</button>
        </div>
      </form>
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

          {isHR && (
            <button className={`nav-item ${activePage === 'Manage policies' ? 'nav-active' : ''}`} onClick={() => goTo('Manage policies')}>
              <span className="nav-icon">⇪</span>
              <span>Manage policies</span>
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
              <span className="profile-role">{isHR ? 'HR admin' : 'Employee workspace'}</span>
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
                      {item.role === 'assistant' && <Citations citations={item.citations} />}
                      {item.role === 'assistant' && <AgentTrace steps={item.trace} />}
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
                <span>Grade · City</span>
                <strong className="stat-small">{[user.grade, user.city].filter(Boolean).join(' · ') || '–'}</strong>
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
