import { useEffect, useRef, useState } from 'react'
import './App.css'

const suggestions = [
{
icon: '🏖️',
title: 'Leave & holidays',
description: 'Understand leave policies and holiday entitlements.',
prompt: 'What is the leave policy for employees?',
},
{
icon: '💰',
title: 'Salary & benefits',
description: 'Learn about compensation and employee benefits.',
prompt: 'What employee benefits are available?',
},
{
icon: '🏢',
title: 'Workplace policies',
description: 'Explore workplace rules and company guidelines.',
prompt: 'What are the workplace policies?',
},
{
icon: '📋',
title: 'Employee eligibility',
description: 'Understand eligibility requirements and criteria.',
prompt: 'What are the employee eligibility criteria?',
},
]

const policyCategories = [
{
icon: '🏖️',
title: 'Leave & attendance',
description: 'Leave entitlements, holidays and attendance guidelines.',
},
{
icon: '💰',
title: 'Compensation & benefits',
description: 'Salary, benefits and compensation-related policies.',
},
{
icon: '🤝',
title: 'Workplace conduct',
description: 'Professional conduct and workplace expectations.',
},
{
icon: '🛡️',
title: 'Employee guidelines',
description: 'Eligibility, employee responsibilities and general guidance.',
},
]

function createConversation() {
return {
id: crypto.randomUUID(),
title: 'New conversation',
messages: [],
updatedAt: Date.now(),
}
}

function getDemoResponse(question) {
const text = question.toLowerCase()

if (text.includes('leave') || text.includes('holiday') || text.includes('vacation')) {
return 'Leave entitlements, approval procedures and holidays depend on your organization’s official HR policy. Check the applicable leave policy or contact HR to confirm your eligibility and available balance. Once connected, HUMANLY can retrieve the relevant policy details.'
}

if (text.includes('salary') || text.includes('benefit') || text.includes('compensation')) {
return 'Salary structures and employee benefits vary by organization, role and eligibility. Please consult your official compensation and benefits documents or HR team for the applicable details. HUMANLY can provide policy-grounded answers once the backend is connected.'
}

if (text.includes('eligible') || text.includes('eligibility')) {
return 'Employee eligibility can depend on employment type, tenure, location and the specific benefit or policy. The applicable HR document should be checked before making a decision. Connect HUMANLY to your policy repository to retrieve the exact criteria.'
}

if (text.includes('workplace') || text.includes('conduct') || text.includes('policy')) {
return 'Workplace policies may cover professional conduct, attendance, confidentiality, safety and employee responsibilities. The exact requirements depend on your organization’s official documentation. HUMANLY will be able to retrieve relevant policy sections after backend integration.'
}

return 'Thanks for your question. This is a frontend demonstration, so I cannot verify your organization’s actual HR policies yet. Once the backend is connected, HUMANLY will be able to search the policy repository and provide a more specific answer.'
}

function App() {
const [message, setMessage] = useState('')
const [activePage, setActivePage] = useState('New chat')
const [sidebarOpen, setSidebarOpen] = useState(false)
const [conversations, setConversations] = useState([])
const [activeConversationId, setActiveConversationId] = useState(null)
const [policySearch, setPolicySearch] = useState('')
const [isTyping, setIsTyping] = useState(false)
const [helpOpen, setHelpOpen] = useState(false)
const messagesEndRef = useRef(null)

const activeConversation = conversations.find(
(conversation) => conversation.id === activeConversationId,
)

const messages = activeConversation?.messages ?? []

const filteredPolicies = policyCategories.filter((policy) => {
const query = policySearch.toLowerCase().trim()
return (
policy.title.toLowerCase().includes(query) ||
policy.description.toLowerCase().includes(query)
)
})

useEffect(() => {
messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
}, [messages, isTyping])

function startNewChat() {
const conversation = createConversation()

setConversations((previous) => [conversation, ...previous])
setActiveConversationId(conversation.id)
setMessage('')
setActivePage('New chat')
setSidebarOpen(false)
setIsTyping(false)

}

function openConversation(conversationId) {
setActiveConversationId(conversationId)
setActivePage('New chat')
setMessage('')
setSidebarOpen(false)
setIsTyping(false)
}

function updateConversation(conversationId, updater) {
setConversations((previous) =>
previous.map((conversation) =>
conversation.id === conversationId
? {
...updater(conversation),
updatedAt: Date.now(),
}
: conversation,
),
)
}

function handleSubmit(event) {
event.preventDefault()

const question = message.trim()
if (!question || isTyping) return

let conversationId = activeConversationId
let isNewConversation = false

if (
  !conversationId ||
  !conversations.some((conversation) => conversation.id === conversationId)
) {
  const conversation = {
    ...createConversation(),
    title: question.length > 36 ? `${question.slice(0, 36)}…` : question,
    messages: [],
  }

  conversationId = conversation.id
  isNewConversation = true
  setActiveConversationId(conversationId)
}

const currentId = conversationId

if (isNewConversation) {
  setConversations((previous) => [
    {
      id: currentId,
      title: question.length > 36 ? `${question.slice(0, 36)}…` : question,
      messages: [{ id: crypto.randomUUID(), role: 'user', content: question }],
      updatedAt: Date.now(),
    },
    ...previous,
  ])
} else {
  updateConversation(currentId, (conversation) => ({
    ...conversation,
    title:
      conversation.messages.length === 0
        ? question.length > 36
          ? `${question.slice(0, 36)}…`
          : question
        : conversation.title,
    messages: [
      ...conversation.messages,
      { id: crypto.randomUUID(), role: 'user', content: question },
    ],
  }))
}

setMessage('')
setActivePage('New chat')
setIsTyping(true)

// Demonstration only: replace this with the backend API call later.
window.setTimeout(() => {
  const answer = getDemoResponse(question)

  updateConversation(currentId, (conversation) => ({
    ...conversation,
    messages: [
      ...conversation.messages,
      { id: crypto.randomUUID(), role: 'assistant', content: answer },
    ],
  }))

  setIsTyping(false)
}, 650)
}

function selectSuggestion(prompt) {
setActivePage('New chat')
setMessage(prompt)
setSidebarOpen(false)
}

function deleteConversation(conversationId) {
setConversations((previous) =>
previous.filter((conversation) => conversation.id !== conversationId),
)

if (activeConversationId === conversationId) {
  setActiveConversationId(null)
  setMessage('')
}
}

function renderComposer() {
return ( <div className="composer-wrapper"> <form className="chat-composer" onSubmit={handleSubmit}>
<textarea
value={message}
onChange={(event) => setMessage(event.target.value)}
placeholder="Ask anything about your HR policies..."
aria-label="Ask a question about HR policies"
rows={2}
onKeyDown={(event) => {
if (
event.key === 'Enter' &&
!event.shiftKey &&
!event.nativeEvent.isComposing
) {
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

        <button
          className="send-button"
          type="submit"
          disabled={!message.trim() || isTyping}
          aria-label="Send message"
        >
          <span>Send</span>
          <span className="send-arrow">↑</span>
        </button>
      </div>
    </form>

    <p className="disclaimer">
      Demo responses are illustrative, not verified HR policy advice.
    </p>
  </div>
)
}

return ( <div className="app-shell">
{sidebarOpen && (
<button
className="sidebar-backdrop"
aria-label="Close navigation"
onClick={() => setSidebarOpen(false)}
/>
)}

  <aside className={`sidebar ${sidebarOpen ? 'sidebar-open' : ''}`}>
    <div className="sidebar-brand">
      <div className="brand-mark">H</div>

      <div className="brand-copy">
        <span className="brand-name">HUMANLY</span>
        <span className="brand-caption">HR INTELLIGENCE</span>
      </div>

      <button
        className="icon-button sidebar-close"
        onClick={() => setSidebarOpen(false)}
        aria-label="Close sidebar"
      >
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

      <button
        className={`nav-item ${activePage === 'New chat' ? 'nav-active' : ''}`}
        onClick={() => {
          setActivePage('New chat')
          setSidebarOpen(false)
        }}
      >
        <span className="nav-icon">✳</span>
        <span>AI Assistant</span>
        <span className="active-indicator" />
      </button>

      <button
        className={`nav-item ${activePage === 'Policy library' ? 'nav-active' : ''}`}
        onClick={() => {
          setActivePage('Policy library')
          setSidebarOpen(false)
        }}
      >
        <span className="nav-icon">▤</span>
        <span>Policy library</span>
      </button>

      <button
        className={`nav-item ${activePage === 'My activity' ? 'nav-active' : ''}`}
        onClick={() => {
          setActivePage('My activity')
          setSidebarOpen(false)
        }}
      >
        <span className="nav-icon">◷</span>
        <span>My activity</span>
      </button>
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
              className={`history-item ${
                activeConversationId === conversation.id ? 'history-item-active' : ''
              }`}
              key={conversation.id}
            >
              <button
                className="history-open"
                onClick={() => openConversation(conversation.id)}
                title={conversation.title}
              >
                <span className="history-symbol">◷</span>
                <span>{conversation.title}</span>
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

      <div className="sidebar-footer">
        <div className="avatar">G</div>

        <div className="profile-copy">
          <span className="profile-name">Guest user</span>
          <span className="profile-role">Employee workspace</span>
        </div>

        <span className="profile-menu">···</span>
      </div>
    </div>
  </aside>

  <main className="main-panel">
    <header className="topbar">
      <div className="topbar-left">
        <button
          className="icon-button mobile-menu"
          onClick={() => setSidebarOpen(true)}
          aria-label="Open navigation"
        >
          ☰
        </button>

        <div className="breadcrumb">
          <span>Workspace</span>
          <span className="breadcrumb-divider">/</span>
          <span className="breadcrumb-current">
            {activePage === 'New chat' && messages.length > 0
              ? activeConversation?.title || 'Conversation'
              : activePage}
          </span>
        </div>
      </div>

      <div className="topbar-right">
        <div className="system-status">
          <span className="status-dot" />
          <span>Frontend demo</span>
        </div>

        <button
          className="help-button"
          aria-label="Help"
          onClick={() => setHelpOpen((previous) => !previous)}
        >
          ?
        </button>
      </div>
    </header>

    {helpOpen && (
      <div className="help-panel" role="status">
        <strong>Welcome to HUMANLY</strong>
        <p>
          Ask a question or select a topic. Responses are demo examples
          until the HR policy backend is connected.
        </p>
        <button onClick={() => setHelpOpen(false)}>Got it</button>
      </div>
    )}

    {activePage === 'New chat' ? (
      messages.length === 0 ? (
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
                <button
                  className="suggestion-card"
                  key={suggestion.title}
                  onClick={() => selectSuggestion(suggestion.prompt)}
                >
                  <div className="suggestion-card-top">
                    <span className={`suggestion-icon suggestion-icon-${index}`}>
                      {suggestion.icon}
                    </span>
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
              <article
                className={`message-row message-${item.role}`}
                key={item.id}
              >
                <div className="message-avatar">
                  {item.role === 'user' ? 'G' : 'H'}
                </div>

                <div className="message-body">
                  <span className="message-author">
                    {item.role === 'user' ? 'You' : 'HUMANLY · Demo'}
                  </span>
                  <p>{item.content}</p>
                </div>
              </article>
            ))}

            {isTyping && (
              <div className="message-row message-assistant">
                <div className="message-avatar">H</div>
                <div className="message-body">
                  <span className="message-author">HUMANLY</span>
                  <p className="typing-indicator">Preparing a demo response…</p>
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
          <p>Explore policy categories and find the guidance you need.</p>
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
            <button
              className="policy-card"
              key={policy.title}
              onClick={() => {
                const relatedSuggestion = suggestions.find((suggestion) =>
                  `${suggestion.title} ${suggestion.description}`
                    .toLowerCase()
                    .includes(policy.title.split(' ')[0].toLowerCase()),
                )

                setActivePage('New chat')
                setMessage(
                  relatedSuggestion?.prompt ||
                    `What should employees know about ${policy.title.toLowerCase()}?`,
                )
              }}
            >
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
          These are demonstration categories, not uploaded company policy documents.
        </p>
      </section>
    ) : (
      <section className="activity-page">
        <div className="page-heading">
          <span className="welcome-eyebrow">YOUR WORKSPACE</span>
          <h1>My activity</h1>
          <p>Review conversations created during this browser session.</p>
        </div>

        <div className="activity-stats">
          <div className="activity-stat">
            <span>Total conversations</span>
            <strong>{conversations.length}</strong>
          </div>
          <div className="activity-stat">
            <span>Questions asked</span>
            <strong>
              {conversations.reduce(
                (total, conversation) =>
                  total +
                  conversation.messages.filter((item) => item.role === 'user').length,
                0,
              )}
            </strong>
          </div>
          <div className="activity-stat">
            <span>Demo responses</span>
            <strong>
              {conversations.reduce(
                (total, conversation) =>
                  total +
                  conversation.messages.filter((item) => item.role === 'assistant').length,
                0,
              )}
            </strong>
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
              <button className="return-button" onClick={startNewChat}>
                Start a conversation →
              </button>
            </div>
          ) : (
            conversations.map((conversation) => (
              <div className="activity-item" key={conversation.id}>
                <div className="activity-item-icon">✳</div>
                <div className="activity-item-copy">
                  <strong>{conversation.title}</strong>
                  <span>
                    {conversation.messages.filter((item) => item.role === 'user').length}{' '}
                    question(s)
                  </span>
                </div>
                <button
                  className="activity-open-button"
                  onClick={() => openConversation(conversation.id)}
                >
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
