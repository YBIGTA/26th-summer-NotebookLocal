// Clean settings page - only server and UI configuration
import { App, PluginSettingTab, Setting } from "obsidian";

export class CopilotSettingTab extends PluginSettingTab {
  plugin: any;

  constructor(app: App, plugin: any) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();

    containerEl.createEl("h2", { text: "Copilot Settings" });

    // Server Configuration
    containerEl.createEl("h3", { text: "Server Configuration" });

    new Setting(containerEl)
      .setName("Server URL")
      .setDesc("URL of the inference server")
      .addText((text) =>
        text
          .setPlaceholder("http://localhost:8000")
          .setValue(this.plugin.settings.serverUrl)
          .onChange(async (value) => {
            this.plugin.settings.serverUrl = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Request Timeout")
      .setDesc("Timeout for API requests (milliseconds)")
      .addText((text) =>
        text
          .setPlaceholder("30000")
          .setValue(this.plugin.settings.timeout.toString())
          .onChange(async (value) => {
            const timeout = parseInt(value) || 30000;
            this.plugin.settings.timeout = timeout;
            await this.plugin.saveSettings();
          })
      );

    // Test Connection
    new Setting(containerEl)
      .setName("Test Connection")
      .setDesc("Test connection to the inference server")
      .addButton((button) =>
        button
          .setButtonText("Test")
          .setCta()
          .onClick(async () => {
            await this.plugin.testConnection();
          })
      );

    // UI Configuration
    containerEl.createEl("h3", { text: "UI Configuration" });

    new Setting(containerEl)
      .setName("Enable Streaming")
      .setDesc("Enable real-time streaming responses")
      .addToggle((toggle) =>
        toggle
          .setValue(this.plugin.settings.enableStreaming)
          .onChange(async (value) => {
            this.plugin.settings.enableStreaming = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Enable Auto-complete")
      .setDesc("Enable auto-completion features")
      .addToggle((toggle) =>
        toggle
          .setValue(this.plugin.settings.enableAutoComplete)
          .onChange(async (value) => {
            this.plugin.settings.enableAutoComplete = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Debug Mode")
      .setDesc("Enable debug logging to console")
      .addToggle((toggle) =>
        toggle
          .setValue(this.plugin.settings.debug)
          .onChange(async (value) => {
            this.plugin.settings.debug = value;
            await this.plugin.saveSettings();
          })
      );

    // Help Section
    containerEl.createEl("h3", { text: "Help" });
    
    const helpDiv = containerEl.createDiv();
    helpDiv.innerHTML = `
      <p><strong>Getting Started:</strong></p>
      <ol>
        <li>Start the inference server on your machine</li>
        <li>Configure the server URL above (default: http://localhost:8000)</li>
        <li>Test the connection</li>
        <li>Use "Upload Document" to add PDF files</li>
        <li>Open the chat view to ask questions</li>
      </ol>
      
      <p><strong>Server not running?</strong></p>
      <p>See the inference-server README for setup instructions.</p>
    `;
  }
}