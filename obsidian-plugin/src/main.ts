// Clean Obsidian Plugin - HTTP Client Only
import { Plugin, WorkspaceLeaf, Notice } from "obsidian";
import { ApiClient } from "./api/ApiClient-clean";
import { getSettings, setSettings } from "./settings/model-clean";
import { CHAT_VIEWTYPE } from "./constants-minimal";
import NotebookLocalView from "./components/NotebookLocalView";

export default class NotebookLocalPlugin extends Plugin {
  // Core components
  apiClient: ApiClient;
  settings: any;

  async onload() {
    console.log("Loading NotebookLocal Plugin");

    // Load settings
    await this.loadSettings();

    // Initialize API client
    this.apiClient = new ApiClient(this.settings);

    // Register chat view
    this.registerView(CHAT_VIEWTYPE, (leaf) => new NotebookLocalView(leaf, this));

    // TODO: Add settings tab when settings UI is ready
    // this.addSettingTab(new CopilotSettingTab(this.app, this));

    // Register commands
    this.addCommands();

    // Add ribbon icon
    this.addRibbonIcon("message-circle", "Open NotebookLocal Chat", () => {
      this.openChatView();
    });

    console.log("NotebookLocal Plugin loaded successfully");
  }

  async onunload() {
    console.log("Unloading NotebookLocal Plugin");
  }

  async loadSettings() {
    this.settings = Object.assign({}, getSettings(), await this.loadData());
  }

  async saveSettings() {
    await this.saveData(this.settings);
    setSettings(this.settings);
    
    // Update API client with new settings
    if (this.apiClient) {
      this.apiClient.updateSettings(this.settings);
    }
  }

  addCommands() {
    // Open Chat Command
    this.addCommand({
      id: "open-chat",
      name: "NotebookLocal: Open Chat",
      callback: () => this.openChatView(),
    });

    // Upload Document Command
    this.addCommand({
      id: "upload-document",
      name: "NotebookLocal: Upload Korean PDF",
      callback: () => this.uploadDocument(),
    });

    // Test Connection Command
    this.addCommand({
      id: "test-connection",
      name: "NotebookLocal: Test Server Connection",
      callback: () => this.testConnection(),
    });
  }

  async openChatView(): Promise<void> {
    // Check if chat view is already open
    const existing = this.app.workspace.getLeavesOfType(CHAT_VIEWTYPE);
    if (existing.length > 0) {
      // Focus existing view
      this.app.workspace.revealLeaf(existing[0]);
      return;
    }

    // Create new chat view in right sidebar
    const leaf = this.app.workspace.getRightLeaf(false);
    await leaf.setViewState({
      type: CHAT_VIEWTYPE,
      active: true,
    });

    // Reveal the new leaf
    this.app.workspace.revealLeaf(leaf);
  }

  async uploadDocument(): Promise<void> {
    // Create file input
    const input = document.createElement("input");
    input.type = "file";
    input.accept = ".pdf";
    input.multiple = false;

    input.onchange = async (event) => {
      const file = (event.target as HTMLInputElement).files?.[0];
      if (!file) return;

      try {
        new Notice("Uploading document...");
        
        const result = await this.apiClient.uploadDocument(file);
        
        new Notice(`Document uploaded successfully: ${result.filename}`);
      } catch (error) {
        console.error("Upload failed:", error);
        new Notice(`Upload failed: ${error.message}`);
      }
    };

    input.click();
  }

  async testConnection(): Promise<void> {
    try {
      new Notice("Testing server connection...");
      
      const health = await this.apiClient.healthCheck();
      
      if (health.status === "healthy") {
        new Notice("✅ Server connection successful!");
      } else {
        new Notice("⚠️ Server responded but may have issues");
      }
    } catch (error) {
      console.error("Connection test failed:", error);
      new Notice(`❌ Connection failed: ${error.message}`);
    }
  }

  // Utility method for other components to access API client
  getApiClient(): ApiClient {
    return this.apiClient;
  }
}