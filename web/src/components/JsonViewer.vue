<script setup lang="ts">
defineProps<{ value: unknown }>()
</script>

<template>
  <pre class="json-viewer">{{ JSON.stringify(value, null, 2) }}</pre>
</template>

