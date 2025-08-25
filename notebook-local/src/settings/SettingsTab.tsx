// Settings Tab for NotebookLocal Plugin
import { App, PluginSettingTab } from "obsidian";
import { createRoot, Root } from "react-dom/client";
import React from "react";
import { StreamingSettings } from "./StreamingSettings";
import { AutoProcessingSettings } from "./AutoProcessingSettings";
import NotebookLocalPlugin from "../main";

export class NotebookLocalSettingTab extends PluginSettingTab {
  plugin: NotebookLocalPlugin;
  private root: Root | null = null;

  constructor(app: App, plugin: NotebookLocalPlugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();
    containerEl.style.userSelect = "text";

    // Create header
    const headerEl = containerEl.createDiv();
    headerEl.style.padding = "20px 0";
    headerEl.style.borderBottom = "1px solid var(--background-modifier-border)";
    headerEl.style.marginBottom = "20px";

    const titleEl = headerEl.createEl("h2");
    titleEl.setText("NotebookLocal Settings");
    titleEl.style.margin = "0";
    titleEl.style.fontSize = "24px";
    titleEl.style.fontWeight = "600";
    titleEl.style.color = "var(--text-normal)";

    const descEl = headerEl.createEl("p");
    descEl.setText("Configure your NotebookLocal AI assistant settings");
    descEl.style.margin = "8px 0 0 0";
    descEl.style.fontSize = "14px";
    descEl.style.color = "var(--text-muted)";

    // Create React container
    const reactContainer = containerEl.createDiv();
    this.root = createRoot(reactContainer);

    // Render React components
    this.root.render(
      <div>
        <StreamingSettings 
          onSettingsChange={() => this.handleSettingsChange()}
        />
        <AutoProcessingSettings 
          onSettingsChange={() => this.handleSettingsChange()}
        />
      </div>
    );
  }

  hide(): void {
    if (this.root) {
      this.root.unmount();
      this.root = null;
    }
  }

  private async handleSettingsChange(): Promise<void> {
    // Save settings when they change
    await this.plugin.saveSettings();
  }
}