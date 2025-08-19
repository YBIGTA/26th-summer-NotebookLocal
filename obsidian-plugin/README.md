# Obsidian Plugin

The frontend component of the RAG Search Pipeline, providing a seamless Obsidian interface for interacting with the inference server. This plugin enables document upload, processing, and AI-powered Q&A directly within your Obsidian workspace.

## 🚀 Features

- **📄 Document Upload**: Upload PDF documents directly from Obsidian
- **💬 Interactive Chat**: Real-time Q&A with your processed documents
- **⚙️ Settings Management**: Configure server connection and plugin options
- **🔍 Document Search**: Search through processed document content
- **📚 Source References**: View document sources for AI responses
- **🎨 Native UI**: Seamlessly integrated with Obsidian's interface

## 📦 Installation

### Method 1: Manual Installation (Recommended for Development)

1. **Clone the repository** (if not already done):
   ```bash
   git clone <repository-url>
   cd rag-search-pipeline/obsidian-plugin/
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```

3. **Build the plugin**:
   ```bash
   npm run build
   ```

4. **Copy to Obsidian plugins directory**:
   ```bash
   # Create plugins directory if it doesn't exist
   mkdir -p ~/.obsidian/plugins/rag-search-plugin/
   
   # Copy built files
   cp -r dist/* ~/.obsidian/plugins/rag-search-plugin/
   cp manifest.json ~/.obsidian/plugins/rag-search-plugin/
   ```

5. **Enable in Obsidian**:
   - Open Obsidian Settings
   - Go to Community Plugins
   - Disable Safe Mode (if enabled)
   - Find "RAG Search Plugin" and enable it

### Method 2: Development Mode

For active development:

1. **Create symlink** to your Obsidian plugins directory:
   ```bash
   ln -s "$(pwd)" ~/.obsidian/plugins/rag-search-plugin
   ```

2. **Run in development mode**:
   ```bash
   npm run dev
   ```

3. **Reload plugin** in Obsidian after code changes:
   - Use Ctrl/Cmd + P → "Reload app without saving"
   - Or disable/enable the plugin in settings

## ⚙️ Configuration

### Prerequisites

1. **Inference Server**: Ensure the inference server is running
   ```bash
   cd ../inference-server/
   uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **OpenAI API Key**: Configure in the inference server's `.env` file

### Plugin Settings

1. **Open Obsidian Settings**
2. **Navigate to Plugin Options** → "RAG Search Plugin"
3. **Configure settings**:
   - **Server URL**: `http://localhost:8000` (default)
   - **API Timeout**: 30 seconds (default)
   - **Auto-connect**: Enable/disable automatic server connection

### Network Configuration

If running the server on a different machine:
```typescript
// In plugin settings
Server URL: http://your-server-ip:8000
```

## 🔧 Usage

### Document Management

1. **Upload Documents**:
   - Open Command Palette (Ctrl/Cmd + P)
   - Search for "RAG: Upload Document"
   - Select PDF file to upload
   - Wait for processing confirmation

2. **View Documents**:
   - Command: "RAG: View Documents"
   - See all processed documents
   - View processing status and metadata

3. **Delete Documents**:
   - Use "RAG: Delete Document" command
   - Select document to remove from index

### Chat Interface

1. **Open Chat**:
   - Command: "RAG: Open Chat"
   - Or click the chat icon in the ribbon

2. **Ask Questions**:
   - Type questions about your uploaded documents
   - Get AI-generated responses with source references
   - View chat history in the interface

3. **Search Documents**:
   - Command: "RAG: Search Documents"
   - Enter search query
   - View relevant document chunks

### Keyboard Shortcuts

Default shortcuts (configurable in Obsidian settings):
- **Ctrl/Cmd + Shift + R**: Open RAG Chat
- **Ctrl/Cmd + Shift + U**: Upload Document
- **Ctrl/Cmd + Shift + S**: Search Documents

## 🏗️ Architecture

### Project Structure

```
obsidian-plugin/
├── src/                           # Source code
│   ├── main.ts                   # Plugin entry point
│   ├── api/                      # Server communication
│   │   └── ApiClient.ts          # HTTP client for inference server
│   ├── components/               # UI components
│   │   ├── Chat.tsx              # Chat interface
│   │   ├── DocumentManager.tsx   # Document management
│   │   └── SettingsPage.tsx      # Plugin settings
│   ├── settings/                 # Configuration management
│   │   └── model.ts              # Settings data models
│   ├── commands/                 # Obsidian commands
│   │   └── index.ts              # Command definitions
│   └── utils/                    # Utility functions
│       └── helpers.ts            # Common helpers
├── manifest.json                 # Plugin metadata
├── package.json                  # Node.js dependencies
├── tsconfig.json                 # TypeScript configuration
├── esbuild.config.mjs           # Build configuration
└── tailwind.config.js           # Styling configuration
```

### Component Overview

- **ApiClient**: Handles all communication with the inference server
- **Chat Component**: Provides real-time chat interface with streaming support
- **Document Manager**: Manages document upload, viewing, and deletion
- **Settings**: Configures server connection and plugin options
- **Commands**: Registers Obsidian commands for plugin functionality

### Communication Flow

```
User Input → Plugin UI → ApiClient → Inference Server → AI Processing → Response → Plugin UI → User
```

## 🛠️ Development

### Development Setup

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Start development server**:
   ```bash
   npm run dev
   ```

3. **Build for production**:
   ```bash
   npm run build
   ```

### Available Scripts

```bash
# Development with hot reload
npm run dev

# Production build
npm run build

# Type checking
npm run type-check

# Linting
npm run lint

# Run tests
npm run test
```

### Adding New Features

1. **Create component** in `src/components/`
2. **Add API methods** in `src/api/ApiClient.ts`
3. **Register commands** in `src/commands/index.ts`
4. **Update settings** if needed in `src/settings/`
5. **Build and test** the plugin

### TypeScript Configuration

The plugin uses strict TypeScript configuration:
```json
{
  "compilerOptions": {
    "strict": true,
    "target": "ES2020",
    "moduleResolution": "node",
    "jsx": "react"
  }
}
```

### Styling

- **Framework**: Tailwind CSS for consistent styling
- **Theme**: Inherits Obsidian's theme colors
- **Components**: Responsive design with mobile support

## 📡 API Integration

### Server Communication

The plugin communicates with the inference server through HTTP requests:

```typescript
// Example: Upload document
const result = await apiClient.processDocument(file);

// Example: Chat with documents
const response = await apiClient.chat({
  message: "What are the main topics?",
  chat_id: "session_123"
});

// Example: Search documents
const results = await apiClient.search({
  query: "machine learning",
  limit: 10
});
```

### Error Handling

- **Connection errors**: Graceful fallback with user notifications
- **API errors**: Detailed error messages for troubleshooting
- **Timeout handling**: Configurable timeouts for long operations
- **Retry logic**: Automatic retry for transient failures

### Streaming Support

Real-time chat responses with server-sent events:
```typescript
await apiClient.chatStream(
  request,
  (chunk) => updateChatUI(chunk),
  () => onComplete(),
  (error) => handleError(error)
);
```

## 🔍 Troubleshooting

### Common Issues

1. **Plugin not loading**:
   - Check if built files exist in plugins directory
   - Verify manifest.json is present
   - Restart Obsidian

2. **Server connection failed**:
   - Verify inference server is running
   - Check server URL in plugin settings
   - Test server health endpoint: `curl http://localhost:8000/api/v1/health`

3. **Document upload fails**:
   - Check file format (PDF only)
   - Verify server has disk space
   - Check server logs for errors

4. **Chat not working**:
   - Ensure documents are uploaded and processed
   - Check API timeout settings
   - Verify OpenAI API key in server configuration

### Debug Mode

Enable debug logging in plugin settings:
```typescript
// In developer console
localStorage.setItem('rag-plugin-debug', 'true');
```

View debug information in browser developer tools (F12).

### Performance Optimization

- **Document caching**: Documents are cached after first upload
- **Lazy loading**: Components load only when needed
- **Request debouncing**: Search queries are debounced to reduce server load
- **Memory management**: Proper cleanup of event listeners and subscriptions

## 🤝 Contributing

1. **Fork the repository**
2. **Create feature branch**: `git checkout -b feature/new-feature`
3. **Make changes** with proper TypeScript types
4. **Test thoroughly** in Obsidian
5. **Submit pull request**

### Code Style

- Follow TypeScript best practices
- Use functional components with hooks
- Implement proper error boundaries
- Add type definitions for all props and state
- Write unit tests for utility functions

### Testing

```bash
# Run unit tests
npm run test

# Test in Obsidian
npm run build && restart Obsidian
```

## 📄 License

This project maintains the same license as the original codebase.

---

**🎉 Happy note-taking with AI-powered document search!**