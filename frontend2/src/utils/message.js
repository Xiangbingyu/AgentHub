export function renderContentBlocks(content) {
  if (typeof content === 'string') {
    return content;
  }
  if (!Array.isArray(content)) {
    return '';
  }
  return content
    .map((block) => {
      if (block.type === 'text') return block.text;
      if (block.type === 'hint') return typeof block.hint === 'string' ? block.hint : '[hint]';
      if (block.type === 'tool_call') return `[tool_call] ${block.name}`;
      if (block.type === 'tool_result') return `[tool_result] ${block.name}`;
      return `[${block.type}]`;
    })
    .join('\n');
}
