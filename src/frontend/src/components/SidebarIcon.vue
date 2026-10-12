<script setup lang="ts">
type IconName = 'workspace' | 'explore' | 'conversation' | 'agent' | 'mcp' | 'knowledge' | 'tool' | 'skill' | 'model' | 'dashboard'

defineProps<{ name: IconName }>()

const paths: Record<IconName, string[]> = {
  workspace: ['M4 3h16a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z', 'M12 16v5M8 21h8M7 7h10M7 11h6'],
  explore: ['M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Z', 'm16 8-2.5 5.5L8 16l2.5-5.5L16 8Z'],
  conversation: ['M21 11.5a8.5 8.5 0 0 1-8.5 8.5H4l-1 1v-9.5A8.5 8.5 0 0 1 11.5 3h1a8.5 8.5 0 0 1 8.5 8.5Z', 'M7 9h10M7 13h7'],
  agent: ['M5 7h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2Z', 'M12 3v4M8 11v2M16 11v2M8 16h8'],
  mcp: ['m9 8 4-4a4.2 4.2 0 0 1 6 6l-4 4', 'm15 16-4 4a4.2 4.2 0 0 1-6-6l4-4', 'm8 16 8-8'],
  knowledge: ['M3 7V5a2 2 0 0 1 2-2h4l3 4h7a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z', 'M3 8h18'],
  tool: ['M4 3h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1ZM16 3h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1ZM4 15h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1ZM16 15h4a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1v-4a1 1 0 0 1 1-1Z'],
  skill: ['m12 3 9 5-9 5-9-5 9-5Z', 'm3 12 9 5 9-5M3 16l9 5 9-5'],
  model: ['m12 3 9 5v8l-9 5-9-5V8l9-5Z', 'm3 8 9 5 9-5M12 13v8'],
  dashboard: ['M4 3h16a1 1 0 0 1 1 1v16a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z', 'M7 16v-5M12 16V7M17 16v-7'],
}
</script>

<template>
  <svg class="sidebar-line-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
    <path v-for="(path, index) in paths[name]" :key="index" :d="path" />
  </svg>
</template>
