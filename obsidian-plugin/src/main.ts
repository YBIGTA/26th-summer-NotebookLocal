// Clean Obsidian Plugin - HTTP Client Only
import { Plugin, WorkspaceLeaf, Notice } from "obsidian";
import { ApiClient } from "./api/ApiClient";
import { getSettings, setSettings } from "./settings/model";
import { CHAT_VIEWTYPE } from "./constants-minimal";

export default class CopilotPlugin extends Plugin {
  // Core components
  apiClient: ApiClient;
  settings: any;

  async onload() {
    console.log("Loading Obsidian Copilot Plugin");

    // Load settings
    await this.loadSettings();

    // Initialize API client
    this.apiClient = new ApiClient(this.settings);

    // TODO: Register views when UI components are ready
    // this.registerView(CHAT_VIEWTYPE, (leaf) => new CopilotView(leaf, this));

    // TODO: Add settings tab when settings UI is ready
    // this.addSettingTab(new CopilotSettingTab(this.app, this));

    // Register commands
    this.addCommands();

    // Add ribbon icon
    this.addRibbonIcon("message-circle", "Open Copilot Chat", () => {
      this.openChatView();
    });

    console.log("Copilot Plugin loaded successfully");
  }

  async onunload() {
    console.log("Unloading Copilot Plugin");
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
      name: "Open Chat",
      callback: () => this.openChatView(),
    });

    // Upload Document Command
    this.addCommand({
      id: "upload-document",
      name: "Upload Document",
      callback: () => this.uploadDocument(),
    });

    // Test Connection Command
    this.addCommand({
      id: "test-connection",
      name: "Test Server Connection",
      callback: () => this.testConnection(),
    });
  }

  async openChatView(): Promise<void> {
    // TODO: Implement when chat view is ready
    new Notice("Chat view coming soon! Use commands for now.");
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