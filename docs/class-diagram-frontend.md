# Class Diagrams — Front End (React, TypeScript, Vite)

*Updated 27 October 2026, after the SOLID refactor (patch 0030). The front end has no classes: it is function
components, hooks and context providers. A **provider** or **module** is drawn as a class with a stereotype, the
props a component takes are its attributes, and `..>` means "uses". Source: `web/src/`.*

Reading order: 1 the shell and providers, 2 the shared API layer, 3 pages and the parts they are built from,
4 shared components, 5 theme, speech and text tools. Section 6 records what the diagrams show about further splits
(cards F1 to F9 in `docs/kanban/cards.json`).

## 1. The shell: providers and routes

```mermaid
flowchart TB
    main["main.tsx"] --> Q[QueryClientProvider]
    Q --> A[AuthProvider<br/>user, logout, deleteAccount]
    A --> P[PreferencesProvider<br/>prefs, update, saveFailed]
    P --> L[ActiveLanguageProvider<br/>active, setActive, studying, info]
    L --> I[I18nProvider<br/>t, tc, err, code]
    I --> T[ThemeProvider<br/>theme, palette, customColors]
    T --> R[BrowserRouter]
    R --> App["App.tsx: Routes"]
    App --> Login["/login"]
    App --> Privacy["/privacy"]
    App --> PL["ProtectedLayout (needs a user)"]
    PL --> Toast[ToastProvider key=user.id]
    Toast --> Confirm[ConfirmProvider]
    Confirm --> Chat[ChatProvider<br/>messages, send, retry, newChat]
    Chat --> Layout["Layout: nav, language switch, Outlet"]
    Layout --> Pages["Home, Vocabulary, Chat, Studio, Library, Practice, Settings, NotFound"]
```

The order matters: preferences need the signed-in user, the active language needs the preferences, the site
language needs both, the theme needs the preferences. `ProtectedLayout` is keyed by the user id so a second learner on
the same browser starts with fresh state; the chat lives only in memory, below that key.

## 2. Contexts and the API layer

```mermaid
classDiagram
    class AuthProvider {
        <<context>>
        +user: User
        +loading: bool
        +setUser(u)
        +logout()
        +logoutAll()
        +deleteAccount(password)
    }
    class PreferencesProvider {
        <<context>>
        +prefs: Prefs
        +ready: bool
        +loggedIn: bool
        +saveFailed: bool
        +update(changes, opts) Promise~bool~
    }
    class DeviceCopy {
        <<module prefs/deviceCopy>>
        +readCopy() Prefs
        +writeCopy(prefs)
        +wipeCopy()
    }
    class ActiveLanguageProvider {
        <<context>>
        +active: string
        +all: LanguageInfo[]
        +studying: LanguageInfo[]
        +setActive(code)
        +info(code) LanguageInfo
    }
    class I18nProvider {
        <<context>>
        +locale: Locale
        +t(key, params) string
        +tc(base, count, params) string
        +err(e, fallbackKey) string
        +code(code, message) string
    }
    class Messages {
        <<module i18n/messages>>
        +MESSAGES: nine-language table
        +MessageKey
        +LOCALES
    }
    class Labels {
        <<module i18n/labels>>
        +typeLabel(t, type) string
        +topicLabel(t, topic) string
        +diffLabel(t, tier) string
    }
    class ThemeProvider {
        <<context>>
        +theme: Theme
        +resolved: light or dark
        +palette: Palette
        +customColors: Colors
        +setTheme(t)
        +setCustomColors(c)
    }
    class ChatProvider {
        <<context>>
        +messages: ChatMessage[]
        +sending: bool
        +send(text, language, setIds)
        +retry(id, language, setIds)
        +newChat()
    }
    class ApiClient {
        <<module api/client: one object, 43 calls>>
        +me() login() register() logout()
        +words() addWord() editWord() deleteWords() moveWords() defineWords() uploadWords()
        +sets() createSet() renameSet() deleteSet()
        +chat()
        +storyOptions() generateStory() saveStory() stories() story() deleteStory()
        +flashcards() choices() cloze()
        +pronounce() translate()
        +myModel() saveMyModel() testMyModel() removeMyModel()
        +savePreferences() updateProfile() changeEmail() changePassword() exportData() health()
    }
    class ApiError {
        +status: int
        +code: string
        +message: string
    }
    class Keys {
        <<module api/keys>>
        +wordsKey(userId, language, ...)
        +storiesKey(userId, ...)
        +setsKey(userId, language)
    }
    class Schema {
        <<generated api/schema.d.ts>>
        from the API's OpenAPI file
    }

    AuthProvider ..> ApiClient : me, logout, deleteAccount
    PreferencesProvider ..> AuthProvider : user
    PreferencesProvider ..> ApiClient : savePreferences
    PreferencesProvider ..> DeviceCopy : copy for signed-out look
    ActiveLanguageProvider ..> PreferencesProvider : active_language
    ActiveLanguageProvider ..> ApiClient : languages
    I18nProvider ..> PreferencesProvider : ui_follows_study_language
    I18nProvider ..> Messages
    ThemeProvider ..> PreferencesProvider : theme, custom_colors
    ChatProvider ..> ApiClient : chat
    ApiClient ..> ApiError : throws
    ApiClient ..> Schema : types
    I18nProvider ..> ApiError : err() turns a code into text
```

Every query key starts with the user id (`Keys`), and `AuthProvider` removes all cached data except `"me"` on
sign-out, so one learner's data can never be shown to the next.

## 3. Pages and the parts they are built from

**3a. Vocabulary** (`routes/Vocabulary.tsx` composes `src/vocab/`; the page keeps the state, the parts get props)

```mermaid
classDiagram
    class Vocabulary {
        <<page, 183 lines>>
        state: search, offset, selected, setFilter, showReading, translating
    }
    class AddWordForm {
        +language +languageName +sets +filter +onChanged
    }
    class SetBar {
        +language +filter +onFilter
    }
    class WordTable {
        +words +selected +readings +setNames
        +onToggle() onToggleAll()
    }
    class MeaningCell {
        +word +language
    }
    class BulkBar {
        +count +sets +translating
        +onMove() onDelete() onClear()
    }
    class Pager {
        +offset +limit +total +onOffset
    }
    class UploadNotice {
        +result
    }
    class UseBulkActions {
        <<hook>>
        +remove: mutation
        +move: mutation
    }
    class DefineLoop {
        <<function>>
        +defineLoop(base, onProgress)
    }
    Vocabulary *-- AddWordForm
    Vocabulary *-- SetBar
    Vocabulary *-- WordTable
    Vocabulary *-- BulkBar
    Vocabulary *-- Pager
    Vocabulary *-- UploadNotice
    Vocabulary ..> UseBulkActions
    Vocabulary ..> DefineLoop
    WordTable *-- MeaningCell
```

**3b. Practice and Settings** (`src/practice/`, `src/settings/`)

```mermaid
classDiagram
    class Practice {
        <<page, 95 lines>>
    }
    class Flashcards {
        +language +set +onDone
    }
    class Choices {
        +language +set +direction +onDone
    }
    class Blanks {
        +storyId +onDone
    }
    class Settings {
        <<page, 67 lines>>
    }
    class Section {
        +title +description
    }
    Practice *-- Flashcards
    Practice *-- Choices
    Practice *-- Blanks
    Settings *-- ProfileSection
    Settings *-- EmailSection
    Settings *-- PasswordSection
    Settings *-- AppearanceSection
    Settings *-- SiteLanguageSection
    Settings *-- MyModelSection
    Settings *-- DataSection
    Settings *-- ServiceRow
    ProfileSection ..> Section
    EmailSection ..> Section
    PasswordSection ..> Section
    AppearanceSection ..> Section
    MyModelSection ..> Section
    DataSection ..> Section
```

**3c. Pages not split yet** (each is one component with local helpers; see section 6)

| Page | Lines | Local pieces | State and requests |
|---|---|---|---|
| `Studio.tsx` | 232 | `customLabel`, `requestedOf`; constants `PRESETS`, `LIMITS`, `CUSTOM` | 10 `useState`, 5 queries and mutations |
| `Login.tsx` | 187 | `PasswordField`, `Field` | two forms (sign in, sign up) |
| `Chat.tsx` | 153 | `SaveStory`, `Waiting` | reads `ChatProvider`; 3 queries and mutations |
| `Privacy.tsx` | 131 | `inline`, `Blocks`, `Th` | policy query |
| `Library.tsx` | 129 | `Opened`, `Row` | 5 queries and mutations |
| `Home.tsx`, `Placeholder.tsx` | 63, 26 | none | none |

## 4. Shared components and what each page uses

```mermaid
classDiagram
    class Ui {
        <<module components/ui>>
        Button Card PageHeader ErrorText
        Spinner Skeleton Badge EmptyState Notice inputCls
    }
    class SetPicker {
        +language +value +onChange +idPrefix
        +setIdsToSend(choice)
        +nothingTicked(choice)
    }
    class StoryReport {
        +report: Report
    }
    class StoryTools {
        +text +language +id
        listen, pronunciation, translate
    }
    class SpeakButton {
        +text +language +label +slow
    }
    class TranslateBox {
        +language +texts +words +idPrefix
    }
    class PronunciationLines {
        +text +language
        +usePronunciation(language, texts, enabled)
    }
    class ToolTrace {
        +call: ToolCall
    }
    class Modal
    class Confirm {
        <<context>>
        +confirm(options) Promise~bool~
    }
    class Toast {
        <<context>>
        +toast(message)
    }
    class Layout
    class ThemeToggle

    Studio ..> SetPicker
    Studio ..> StoryReport
    Studio ..> StoryTools
    Chat ..> SetPicker
    Chat ..> StoryTools
    Chat ..> ToolTrace
    Library ..> StoryReport
    Library ..> StoryTools
    Library ..> Confirm
    Vocabulary ..> TranslateBox
    Vocabulary ..> PronunciationLines : usePronunciation
    StoryTools *-- PronunciationLines
    StoryTools *-- TranslateBox
    StoryTools *-- SpeakButton
    Vocabulary ..> SpeakButton
    Flashcards ..> SpeakButton
    Choices ..> SpeakButton
    Confirm ..> Modal : renders in
    Layout *-- ThemeToggle
    DataSection ..> Modal : delete account
```

## 5. Theme, speech and text helpers (pure modules)

```mermaid
classDiagram
    class Color {
        <<module theme/color>>
        +hexToRgb() rgbToHex() hsvToRgb()
        +luminance(c) number
        +contrast(a, b) number
        +mix(a, b, t) string
    }
    class Palette {
        <<module theme/palette>>
        +PRESETS
        +derivePalette(colors) Palette
        +validColors(c) bool
    }
    class Wheel {
        <<module theme/wheel>>
        +pointToHueStrength(point)
        +hueStrengthToPoint(h, s)
        +keyStep(key)
    }
    class ColorWheel {
        <<component>>
        +value +onChange
    }
    class Speak {
        <<module speech/speak>>
        +SPEECH_LANG
        +speechSupported() bool
        +chunks(text) string[]
        +voiceFor(language) Voice
        +speak(text, language, handlers)
    }

    Palette --> Color
    ColorWheel --> Wheel
    ColorWheel --> Color
    AppearanceSection ..> Palette
    AppearanceSection ..> ColorWheel
    SpeakButton ..> Speak
    TranslateBox ..> Speak : chunks
```

## 6. What these diagrams show about further splits

Findings are ranked by value for easier maintenance. Each has a kanban card (cards "F1" to "F9" in
`docs/kanban/cards.json`). None is built yet; each keeps screens and labels unchanged and keeps the 269 web tests as the safety net.

| # | Where | What the diagram shows | Proposed split | Principle |
|---|---|---|---|---|
| F1 | `api/client.ts` | One object with 43 calls: every page depends on the whole API, and the file grows with every feature | Per-area modules (`api/words.ts`, `stories.ts`, `account.ts`, `practice.ts`, `text.ts`, ...) re-exported as the same `api` object | I, S |
| F2 | `routes/Studio.tsx` (232 lines) | 10 pieces of state, 5 queries and mutations, the difficulty presets and limits, the custom-kind logic and the result view in one component | `studio/OptionsForm`, `studio/DifficultyPicker` (with the presets), `studio/GeneratedStory` (result, save), a `useStoryGeneration` hook | S |
| F3 | `routes/Login.tsx` (187 lines) | Two forms (sign in, sign up) and two field helpers in one page | `auth/LoginForm`, `auth/RegisterForm`, `auth/fields.tsx`; the page chooses the tab | S |
| F4 | `Studio.PRESETS` and `LIMITS` | The three difficulty sizes are written in the page and again in `tutor_core/difficulty.py` | Serve them from `GET /api/stories/options` so the server is the only copy | DRY |
| F5 | `routes/Chat.tsx` (153 lines) | The message list, the composer, the retry and the story-save button in one page | `chat/MessageList`, `chat/Composer`, `chat/SaveStory`; `useChat` stays in the provider | S |
| F6 | Studio and Library | Both show a story's type, topic and difficulty with the same three label helpers and a badge row | One `components/StoryMeta` component | DRY |
| F7 | `i18n/messages.ts` (471 lines) | One table for every page's text, so any page change edits the same file | `i18n/messages/` split by area (`common`, `vocab`, `studio`, `settings`, ...) merged in an index; the compile-time check for a missing translation stays | S, O |
| F8 | `prefs/PreferencesProvider.tsx` (162 lines) | Server sync, debounce and the device copy in one provider | A `useSavedPreferences` hook (debounce and retry) plus the provider that only holds the value | S |
| F9 | `routes/Library.tsx` (129 lines) and `Privacy.tsx` (131 lines) | `Library` holds the list, the row, the opened story and the delete flow; `Privacy` holds a small renderer for the policy blocks | `library/StoryRow`, `library/OpenedStory`; `privacy/PolicyBlocks` | S |

Not worth splitting (checked): the context providers other than preferences (each is under 125 lines with one
reason to change), `components/ui.tsx` (ten tiny primitives that change together), `theme/` (already split into
colour math, palette, wheel and component), and `Settings.tsx` after patch 0030 (67 lines).
