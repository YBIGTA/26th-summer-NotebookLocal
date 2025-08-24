"""
MaintainEngine - Vault health and organization suggestions.

Core behaviors:
- Identify issues without user asking
- Suggest fixes, don't force them
- Preserve user's organizational system
- Batch similar fixes for efficiency
"""

import logging
import time
from typing import Dict, List, Any, Set
import re
from collections import defaultdict

from .base_engine import BaseEngine, EngineResponse
from ..context_engine import ContextPyramid
from ..intent_detector import DetectedIntent

logger = logging.getLogger(__name__)

class MaintainEngine(BaseEngine):
    """Keep vault healthy and well-organized."""
    
    def __init__(self, llm_router):
        super().__init__(llm_router, "MaintainEngine")
    
    async def process(
        self,
        message: str,
        intent: DetectedIntent,
        context: ContextPyramid
    ) -> EngineResponse:
        """Process MAINTAIN intent for vault health and organization."""
        
        start_time = time.time()
        self.logger.info(f"🔧 Processing MAINTAIN query: {intent.sub_capability}")
        
        try:
            # Route to specific maintenance capability
            if intent.sub_capability == 'health_check':
                return await self._handle_health_check(message, context)
            elif intent.sub_capability == 'fix_links':
                return await self._handle_fix_links(message, context)
            elif intent.sub_capability == 'organize':
                return await self._handle_organize(message, context)
            elif intent.sub_capability == 'find_duplicates':
                return await self._handle_find_duplicates(message, context)
            else:
                return await self._handle_general_maintenance(message, context)
                
        except Exception as e:
            self.logger.error(f"Error in MaintainEngine: {e}")
            
            return EngineResponse(
                content=f"I had trouble analyzing your vault health: {str(e)}",
                confidence=0.0,
                metadata={'error': str(e)},
                suggested_actions=["Try a more specific maintenance request"],
                processing_time=time.time() - start_time
            )
    
    async def _handle_health_check(self, message: str, context: ContextPyramid) -> EngineResponse:
        """Perform comprehensive vault health analysis."""
        
        health_analysis = self._analyze_vault_health(context)
        
        # Format health report
        content_parts = ["# Vault Health Report\n"]
        
        # Overall status
        overall_score = health_analysis['overall_score']
        if overall_score >= 0.8:
            status = "🟢 Excellent"
        elif overall_score >= 0.6:
            status = "🟡 Good"
        else:
            status = "🔴 Needs attention"
        
        content_parts.append(f"**Overall Health:** {status} ({overall_score:.1%})\n")
        
        # Specific issues
        if health_analysis['broken_links']:
            content_parts.append(f"🔴 **Broken Links:** {len(health_analysis['broken_links'])} found")
            for link in health_analysis['broken_links'][:5]:
                content_parts.append(f"  - [[{link}]] in {link.get('source', 'unknown')}")
            if len(health_analysis['broken_links']) > 5:
                content_parts.append(f"  - ... and {len(health_analysis['broken_links']) - 5} more")
            content_parts.append("")
        
        if health_analysis['orphan_notes']:
            content_parts.append(f"🟡 **Orphan Notes:** {len(health_analysis['orphan_notes'])} found")
            for note in health_analysis['orphan_notes'][:3]:
                content_parts.append(f"  - {note}")
            content_parts.append("")
        
        if health_analysis['duplicate_candidates']:
            content_parts.append(f"🟡 **Potential Duplicates:** {len(health_analysis['duplicate_candidates'])} pairs")
            for pair in health_analysis['duplicate_candidates'][:3]:
                content_parts.append(f"  - {pair[0]} ↔ {pair[1]} (similarity: {pair[2]:.1%})")
            content_parts.append("")
        
        # Suggestions
        content_parts.append("## Recommendations")
        if health_analysis['suggestions']:
            for suggestion in health_analysis['suggestions']:
                content_parts.append(f"- {suggestion}")
        else:
            content_parts.append("- Your vault looks healthy! Keep up the good organization.")
        
        suggestions = [
            "Fix broken links first (highest priority)",
            "Review orphan notes for potential connections",
            "Schedule regular health checks"
        ]
        
        return EngineResponse(
            content='\n'.join(content_parts),
            confidence=0.9,  # High confidence in health analysis
            metadata={
                'health_score': overall_score,
                'issues_found': len(health_analysis['broken_links']) + len(health_analysis['orphan_notes']),
                'suggestions_count': len(health_analysis['suggestions'])
            },
            suggested_actions=suggestions,
            processing_time=time.time() - time.time()
        )
    
    async def _handle_fix_links(self, message: str, context: ContextPyramid) -> EngineResponse:
        """Handle broken link fixing."""
        
        broken_links = self._find_broken_links(context)
        
        if not broken_links:
            content = "🟢 No broken links found in the analyzed content!"
        else:
            content_parts = [f"Found {len(broken_links)} broken links:\n"]
            
            for link_info in broken_links[:10]:
                content_parts.append(f"- [[{link_info['link']}]] in {link_info['source']}")
                if link_info['suggestions']:
                    content_parts.append(f"  Suggestions: {', '.join(link_info['suggestions'])}")
            
            content = '\n'.join(content_parts)
        
        suggestions = [
            "Fix links one by one manually",
            "Batch update similar link patterns",
            "Create missing notes for broken links"
        ]
        
        return EngineResponse(
            content=content,
            confidence=0.9,
            metadata={'broken_links_count': len(broken_links)},
            suggested_actions=suggestions,
            processing_time=time.time() - time.time()
        )
    
    async def _handle_organize(self, message: str, context: ContextPyramid) -> EngineResponse:
        """Handle organization suggestions."""
        
        context_text = self._format_context_simple(context)
        
        response_text = await self._query_llm_with_templates(
            sub_capability='organize',
            message=message,
            context=context_text
        )
        
        return EngineResponse(
            content=response_text,
            confidence=0.7,
            metadata={'organization_type': 'structure_improvement'},
            suggested_actions=[
                "Implement one organization suggestion at a time",
                "Create index notes for better navigation",
                "Use consistent naming conventions"
            ],
            processing_time=time.time() - time.time()
        )
    
    async def _handle_find_duplicates(self, message: str, context: ContextPyramid) -> EngineResponse:
        """Find potentially duplicate content."""
        
        duplicates = self._find_duplicate_candidates(context)
        
        if not duplicates:
            content = "🟢 No obvious duplicate content found!"
        else:
            content_parts = [f"Found {len(duplicates)} potential duplicate pairs:\n"]
            
            for pair in duplicates[:5]:
                similarity = pair['similarity']
                content_parts.append(f"- **{pair['file1']}** ↔ **{pair['file2']}** (similarity: {similarity:.1%})")
                content_parts.append(f"  Reason: {pair['reason']}\n")
            
            content = '\n'.join(content_parts)
        
        return EngineResponse(
            content=content,
            confidence=0.8,
            metadata={'duplicate_pairs': len(duplicates)},
            suggested_actions=[
                "Review duplicate pairs manually",
                "Merge truly duplicate content",
                "Keep distinct notes that seem similar but serve different purposes"
            ],
            processing_time=time.time() - time.time()
        )
    
    async def _handle_general_maintenance(self, message: str, context: ContextPyramid) -> EngineResponse:
        """Handle general maintenance requests."""
        
        # Perform broad health analysis
        health_analysis = self._analyze_vault_health(context)
        analysis_text = self._format_health_analysis(health_analysis)
        
        response_text = await self._query_llm_with_templates(
            sub_capability='general',
            message=message,
            context=analysis_text,
            template_variables={
                'broken_links_count': len(health_analysis.get('broken_links', [])),
                'orphans_count': len(health_analysis.get('orphans', [])),
                'total_files': len(health_analysis.get('files', []))
            }
        )
        
        return EngineResponse(
            content=response_text,
            confidence=0.8,
            metadata={'maintenance_type': 'general'},
            suggested_actions=[
                "Start with highest priority issues",
                "Set up regular maintenance schedule",
                "Focus on one type of issue at a time"
            ],
            processing_time=time.time() - time.time()
        )
    
    def _analyze_vault_health(self, context: ContextPyramid) -> Dict[str, Any]:
        """Analyze vault health from context items."""
        
        all_links = set()
        existing_files = set()
        orphan_candidates = []
        link_sources = defaultdict(list)
        
        # Analyze each note
        for item in context.items:
            file_path = item.source_path
            content = item.content
            existing_files.add(file_path)
            
            # Extract all links
            links = re.findall(r'\[\[([^\]]+)\]\]', content)
            for link in links:
                clean_link = link.split('|')[0]  # Remove aliases
                all_links.add(clean_link)
                link_sources[clean_link].append(file_path)
            
            # Check for orphan status (no incoming links)
            incoming_links = 0
            for other_item in context.items:
                if other_item.source_path != file_path:
                    if file_path in other_item.content or item.source_path.split('/')[-1].replace('.md', '') in other_item.content:
                        incoming_links += 1
            
            if incoming_links == 0 and len(links) == 0:  # No in or out links
                orphan_candidates.append(file_path)
        
        # Find broken links
        broken_links = []
        for link in all_links:
            # Check if link target exists (simple check)
            link_variations = [link, f"{link}.md", link.replace(' ', '-')]
            found = any(variation in {item.source_path for item in context.items} for variation in link_variations)
            
            if not found:
                broken_links.append({
                    'link': link,
                    'sources': link_sources[link],
                    'suggestions': self._suggest_link_fixes(link, existing_files)
                })
        
        # Find potential duplicates (very basic)
        duplicate_candidates = self._find_duplicate_candidates(context)
        
        # Calculate overall health score
        total_items = len(context.items)
        issues = len(broken_links) + len(orphan_candidates) + len(duplicate_candidates)
        overall_score = max(0.0, 1.0 - (issues / max(1, total_items)))
        
        # Generate suggestions
        suggestions = []
        if broken_links:
            suggestions.append(f"Fix {len(broken_links)} broken links")
        if orphan_candidates:
            suggestions.append(f"Connect {len(orphan_candidates)} orphan notes")
        if duplicate_candidates:
            suggestions.append(f"Review {len(duplicate_candidates)} potential duplicates")
        if not suggestions:
            suggestions.append("Consider creating index notes for better navigation")
        
        return {
            'overall_score': overall_score,
            'broken_links': broken_links,
            'orphan_notes': orphan_candidates,
            'duplicate_candidates': duplicate_candidates,
            'total_links': len(all_links),
            'total_files': total_items,
            'suggestions': suggestions
        }
    
    def _find_broken_links(self, context: ContextPyramid) -> List[Dict[str, Any]]:
        """Find broken links in context."""
        
        all_files = {item.source_path for item in context.items}
        broken_links = []
        
        for item in context.items:
            links = re.findall(r'\[\[([^\]]+)\]\]', item.content)
            
            for link in links:
                clean_link = link.split('|')[0]  # Remove alias
                
                # Check if target exists
                possible_targets = [
                    clean_link,
                    f"{clean_link}.md",
                    clean_link.replace(' ', '-'),
                    clean_link.replace(' ', '_')
                ]
                
                found = any(target in all_files for target in possible_targets)
                
                if not found:
                    broken_links.append({
                        'link': clean_link,
                        'source': item.source_path,
                        'suggestions': self._suggest_link_fixes(clean_link, all_files)
                    })
        
        return broken_links
    
    def _suggest_link_fixes(self, broken_link: str, existing_files: Set[str]) -> List[str]:
        """Suggest fixes for broken links."""
        
        suggestions = []
        broken_lower = broken_link.lower()
        
        # Find similar file names
        for file_path in existing_files:
            file_name = file_path.split('/')[-1].replace('.md', '')
            file_lower = file_name.lower()
            
            # Simple similarity check
            if file_lower in broken_lower or broken_lower in file_lower:
                suggestions.append(file_name)
            elif self._similar_strings(broken_lower, file_lower):
                suggestions.append(file_name)
        
        return suggestions[:3]
    
    def _similar_strings(self, s1: str, s2: str, threshold: float = 0.7) -> bool:
        """Check if two strings are similar (basic implementation)."""
        
        # Simple character overlap similarity
        set1 = set(s1)
        set2 = set(s2)
        
        if not set1 or not set2:
            return False
        
        overlap = len(set1 & set2)
        total = len(set1 | set2)
        
        return overlap / total >= threshold
    
    def _find_duplicate_candidates(self, context: ContextPyramid) -> List[Dict[str, Any]]:
        """Find potential duplicate content."""
        
        candidates = []
        items = context.items
        
        for i, item1 in enumerate(items):
            for j, item2 in enumerate(items[i+1:], i+1):
                similarity = self._calculate_content_similarity(item1.content, item2.content)
                
                if similarity >= 0.7:  # High similarity threshold
                    candidates.append({
                        'file1': item1.source_path,
                        'file2': item2.source_path,
                        'similarity': similarity,
                        'reason': self._explain_similarity(item1.content, item2.content)
                    })
        
        return candidates
    
    def _calculate_content_similarity(self, content1: str, content2: str) -> float:
        """Calculate similarity between two pieces of content."""
        
        # Simple word-based similarity
        words1 = set(re.findall(r'\b\w+\b', content1.lower()))
        words2 = set(re.findall(r'\b\w+\b', content2.lower()))
        
        if not words1 or not words2:
            return 0.0
        
        overlap = len(words1 & words2)
        total = len(words1 | words2)
        
        return overlap / total if total > 0 else 0.0
    
    def _explain_similarity(self, content1: str, content2: str) -> str:
        """Explain why two pieces of content are similar."""
        
        # Find common themes
        words1 = set(re.findall(r'\b\w+\b', content1.lower()))
        words2 = set(re.findall(r'\b\w+\b', content2.lower()))
        common_words = words1 & words2
        
        # Filter out common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'from', 'with', 'by'}
        meaningful_words = common_words - stop_words
        
        if meaningful_words:
            return f"Share keywords: {', '.join(list(meaningful_words)[:5])}"
        else:
            return "Similar structure or length"
    
    def _format_health_analysis(self, analysis: Dict[str, Any]) -> str:
        """Format health analysis for LLM consumption."""
        
        lines = [
            f"Overall health score: {analysis['overall_score']:.1%}",
            f"Total files analyzed: {analysis['total_files']}",
            f"Broken links: {len(analysis['broken_links'])}",
            f"Orphan notes: {len(analysis['orphan_notes'])}",
            f"Potential duplicates: {len(analysis['duplicate_candidates'])}"
        ]
        
        return '\n'.join(lines)
    
    def _format_context_simple(self, context: ContextPyramid) -> str:
        """Simple context formatting for LLM."""
        if not context.items:
            return "No relevant context found."
        
        sections = []
        for item in context.items:
            sections.append(f"\n--- {item.source_path} ---\n{item.content}")
        
        return f"CONTEXT FROM YOUR VAULT:\n{''.join(sections)}"