// Email Builder - Drag and Drop with Blocks
class EmailBuilder {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.blocks = [];
        this.selectedBlock = null;
        this.options = {
            onChange: options.onChange || (() => {}),
            mergeFields: options.mergeFields || ['first_name', 'last_name', 'email', 'company']
        };
        
        this.blockTypes = {
            heading: { label: 'Heading', icon: 'type', defaultContent: 'Email Title' },
            paragraph: { label: 'Paragraph', icon: 'justify-left', defaultContent: 'Write your message here...' },
            button: { label: 'Button', icon: 'cursor-text', defaultContent: 'Click Here', styles: { text: 'Click Here', url: '#', bg: '#2E7D32', color: '#ffffff' } },
            image: { label: 'Image', icon: 'image', defaultContent: '', styles: { url: 'https://via.placeholder.com/600x200', alt: 'Image' } },
            divider: { label: 'Divider', icon: 'horizontal-rule', defaultContent: '' },
            spacer: { label: 'Spacer', icon: 'arrows-vertical', defaultContent: '', styles: { height: '20px' } },
            columns2: { label: '2 Columns', icon: 'columns', isLayout: true },
            columns3: { label: '3 Columns', icon: 'layout-columns', isLayout: true }
        };
        
        this.init();
    }
    
    init() {
        this.renderToolbar();
        this.renderEditor();
        this.renderPreview();
    }
    
    renderToolbar() {
        const toolbar = document.createElement('div');
        toolbar.className = 'email-builder-toolbar';
        toolbar.innerHTML = `
            <div class="toolbar-section">
                <strong>Add Block:</strong>
                ${Object.entries(this.blockTypes).map(([type, config]) => `
                    <button type="button" class="btn btn-outline-secondary btn-sm" onclick="emailBuilder.addBlock('${type}')">
                        <i class="bi bi-${config.icon}"></i> ${config.label}
                    </button>
                `).join('')}
            </div>
            <div class="toolbar-section">
                <button type="button" class="btn btn-success btn-sm" onclick="emailBuilder.exportHtml()">
                    <i class="bi bi-code"></i> Export HTML
                </button>
                <button type="button" class="btn btn-primary btn-sm" onclick="emailBuilder.previewEmail()">
                    <i class="bi bi-eye"></i> Preview
                </button>
            </div>
        `;
        this.container.appendChild(toolbar);
    }
    
    renderEditor() {
        const editor = document.createElement('div');
        editor.className = 'email-builder-editor';
        editor.id = 'block-editor';
        editor.innerHTML = '<div class="blocks-container" id="blocks-container"></div>';
        this.container.appendChild(editor);
        this.blocksContainer = editor.querySelector('#blocks-container');
    }
    
    renderPreview() {
        const preview = document.createElement('div');
        preview.className = 'email-builder-preview';
        preview.id = 'email-preview';
        preview.innerHTML = '<div class="preview-content" id="preview-content"></div>';
        this.container.appendChild(preview);
        this.previewContent = preview.querySelector('#preview-content');
    }
    
    addBlock(type) {
        const blockConfig = this.blockTypes[type];
        const block = {
            id: 'block-' + Date.now(),
            type: type,
            content: blockConfig.defaultContent,
            styles: blockConfig.styles ? { ...blockConfig.styles } : {}
        };
        
        if (type === 'columns2') {
            block.columns = [{}, {}];
        } else if (type === 'columns3') {
            block.columns = [{}, {}, {}];
        }
        
        this.blocks.push(block);
        this.renderBlocks();
        this.options.onChange(this.getBlocks());
    }
    
    renderBlocks() {
        this.blocksContainer.innerHTML = this.blocks.map((block, index) => this.renderBlock(block, index)).join('');
        this.attachBlockListeners();
    }
    
    renderBlock(block, index) {
        const isSelected = this.selectedBlock === block.id;
        let blockContent = '';
        
        switch (block.type) {
            case 'heading':
                blockContent = `<input type="text" class="form-control" value="${this.escapeHtml(block.content)}" 
                    onchange="emailBuilder.updateBlock(${index}, 'content', this.value)" 
                    style="font-size: 24px; font-weight: bold;">`;
                break;
            case 'paragraph':
                blockContent = `<textarea class="form-control" rows="4"
                    onchange="emailBuilder.updateBlock(${index}, 'content', this.value)"
                    >${this.escapeHtml(block.content)}</textarea>
                    ${this.renderMergeFields(index, 'content')}`;
                break;
            case 'button':
                blockContent = `
                    <div class="row g-2">
                        <div class="col-6">
                            <input type="text" class="form-control" placeholder="Button Text" value="${block.styles.text || ''}"
                            onchange="emailBuilder.updateBlockStyle(${index}, 'text', this.value)">
                        </div>
                        <div class="col-6">
                            <input type="text" class="form-control" placeholder="URL" value="${block.styles.url || ''}"
                            onchange="emailBuilder.updateBlockStyle(${index}, 'url', this.value)">
                        </div>
                        <div class="col-6">
                            <input type="color" class="form-control" value="${block.styles.bg || '#2E7D32'}"
                            onchange="emailBuilder.updateBlockStyle(${index}, 'bg', this.value)">
                        </div>
                        <div class="col-6">
                            <input type="color" class="form-control" value="${block.styles.color || '#ffffff'}"
                            onchange="emailBuilder.updateBlockStyle(${index}, 'color', this.value)">
                        </div>
                    </div>
                    ${this.renderMergeFields(index, 'styles.text')}`;
                break;
            case 'image':
                blockContent = `
                    <div class="row g-2">
                        <div class="col-12">
                            <input type="text" class="form-control" placeholder="Image URL" value="${block.styles.url || ''}"
                            onchange="emailBuilder.updateBlockStyle(${index}, 'url', this.value)">
                        </div>
                        <div class="col-12">
                            <input type="text" class="form-control" placeholder="Alt Text" value="${block.styles.alt || ''}"
                            onchange="emailBuilder.updateBlockStyle(${index}, 'alt', this.value)">
                        </div>
                    </div>`;
                break;
            case 'divider':
                blockContent = '<hr>';
                break;
            case 'spacer':
                blockContent = `<input type="range" class="form-range" min="10" max="100" value="${parseInt(block.styles.height) || 20}"
                    oninput="emailBuilder.updateBlockStyle(${index}, 'height', this.value + 'px')">`;
                break;
            case 'columns2':
            case 'columns3':
                blockContent = `<div class="row">
                    ${(block.columns || []).map((col, colIdx) => `
                        <div class="col">
                            <div class="p-2 border rounded" style="min-height: 60px;">
                                <small class="text-muted">Column ${colIdx + 1}</small>
                            </div>
                        </div>
                    `).join('')}
                </div>`;
                break;
        }
        
        return `
            <div class="block-item ${isSelected ? 'selected' : ''}" data-block-id="${block.id}" draggable="true">
                <div class="block-header">
                    <span class="block-type">${this.blockTypes[block.type].label}</span>
                    <div class="block-actions">
                        <button type="button" class="btn btn-sm btn-outline-danger" onclick="emailBuilder.deleteBlock(${index})">
                            <i class="bi bi-trash"></i>
                        </button>
                    </div>
                </div>
                <div class="block-content">
                    ${blockContent}
                </div>
            </div>
        `;
    }
    
    renderMergeFields(blockIndex, field) {
        return `
            <div class="mt-2">
                <small class="text-muted">Insert:</small>
                ${this.options.mergeFields.map(field => `
                    <button type="button" class="btn btn-xs btn-outline-info" 
                        onclick="emailBuilder.insertMergeField(${blockIndex}, '${field}', '{{${field}}}')">
                        {{${field}}}
                    </button>
                `).join('')}
            </div>
        `;
    }
    
    insertMergeField(blockIndex, field, value) {
        const block = this.blocks[blockIndex];
        if (field === 'styles.text') {
            block.styles.text = (block.styles.text || '') + value;
        } else {
            block.content = (block.content || '') + value;
        }
        this.renderBlocks();
        this.renderPreviewHtml();
        this.options.onChange(this.getBlocks());
    }
    
    updateBlock(index, field, value) {
        this.blocks[index][field] = value;
        this.renderPreviewHtml();
        this.options.onChange(this.getBlocks());
    }
    
    updateBlockStyle(index, style, value) {
        this.blocks[index].styles[style] = value;
        this.renderPreviewHtml();
        this.options.onChange(this.getBlocks());
    }
    
    deleteBlock(index) {
        this.blocks.splice(index, 1);
        this.selectedBlock = null;
        this.renderBlocks();
        this.renderPreviewHtml();
        this.options.onChange(this.getBlocks());
    }
    
    attachBlockListeners() {
        document.querySelectorAll('.block-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (!e.target.closest('button') && !e.target.closest('input') && !e.target.closest('textarea')) {
                    this.selectedBlock = item.dataset.blockId;
                    this.renderBlocks();
                }
            });
            
            item.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('text/plain', item.dataset.blockId);
            });
            
            item.addEventListener('dragover', (e) => {
                e.preventDefault();
            });
            
            item.addEventListener('drop', (e) => {
                e.preventDefault();
                const draggedId = e.dataTransfer.getData('text/plain');
                this.reorderBlocks(draggedId, item.dataset.blockId);
            });
        });
    }
    
    reorderBlocks(draggedId, targetId) {
        const draggedIndex = this.blocks.findIndex(b => b.id === draggedId);
        const targetIndex = this.blocks.findIndex(b => b.id === targetId);
        
        const [draggedBlock] = this.blocks.splice(draggedIndex, 1);
        this.blocks.splice(targetIndex, 0, draggedBlock);
        
        this.renderBlocks();
        this.renderPreviewHtml();
        this.options.onChange(this.getBlocks());
    }
    
    renderPreviewHtml() {
        let html = '';
        
        this.blocks.forEach(block => {
            switch (block.type) {
                case 'heading':
                    html += `<h1 style="margin: 0 0 16px 0; color: #333;">${this.escapeHtml(block.content)}</h1>`;
                    break;
                case 'paragraph':
                    html += `<p style="margin: 0 0 16px 0; line-height: 1.6;">${this.escapeHtml(block.content).replace(/\n/g, '<br>')}</p>`;
                    break;
                case 'button':
                    const text = block.styles.text || 'Click Here';
                    const url = block.styles.url || '#';
                    const bg = block.styles.bg || '#2E7D32';
                    const color = block.styles.color || '#ffffff';
                    html += `<p style="margin: 0 0 16px 0; text-align: center;">
                        <a href="${url}" style="display: inline-block; padding: 12px 24px; background: ${bg}; color: ${color}; text-decoration: none; border-radius: 4px; font-weight: bold;">${this.escapeHtml(text)}</a>
                    </p>`;
                    break;
                case 'image':
                    const imgUrl = block.styles.url || 'https://via.placeholder.com/600x200';
                    const imgAlt = block.styles.alt || 'Image';
                    html += `<p style="margin: 0 0 16px 0; text-align: center;">
                        <img src="${imgUrl}" alt="${imgAlt}" style="max-width: 100%; height: auto;">
                    </p>`;
                    break;
                case 'divider':
                    html += `<hr style="border: none; border-top: 1px solid #ddd; margin: 16px 0;">`;
                    break;
                case 'spacer':
                    const height = block.styles.height || '20px';
                    html += `<div style="height: ${height};"></div>`;
                    break;
                case 'columns2':
                    html += `<table width="100%" cellpadding="0" cellspacing="0" style="margin: 0 0 16px 0;"><tr><td width="50%" valign="top">Column 1</td><td width="50%" valign="top">Column 2</td></tr></table>`;
                    break;
                case 'columns3':
                    html += `<table width="100%" cellpadding="0" cellspacing="0" style="margin: 0 0 16px 0;"><tr><td width="33%" valign="top">Column 1</td><td width="34%" valign="top">Column 2</td><td width="33%" valign="top">Column 3</td></tr></table>`;
                    break;
            }
        });
        
        this.previewContent.innerHTML = html;
        return html;
    }
    
    exportHtml() {
        const html = this.renderPreviewHtml();
        const fullHtml = this.wrapInEmailTemplate(html);
        
        navigator.clipboard.writeText(fullHtml).then(() => {
            alert('HTML copied to clipboard!');
        }).catch(() => {
            prompt('Copy this HTML:', fullHtml);
        });
    }
    
    previewEmail() {
        const html = this.wrapInEmailTemplate(this.renderPreviewHtml());
        const win = window.open('', '_blank');
        win.document.write(html);
        win.document.close();
    }
    
    wrapInEmailTemplate(content) {
        return `<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email</title>
</head>
<body style="margin: 0; padding: 20px; background-color: #f5f5f5;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden;">
        <tr>
            <td style="padding: 20px;">
                ${content}
            </td>
        </tr>
    </table>
</body>
</html>`;
    }
    
    getBlocks() {
        return this.blocks;
    }
    
    setBlocks(blocks) {
        this.blocks = blocks;
        this.renderBlocks();
        this.renderPreviewHtml();
    }
    
    escapeHtml(text) {
        if (!text) return '';
        return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
    
    loadTemplate(templateName) {
        const templates = {
            welcome: [
                { type: 'heading', content: 'Welcome to Our Community!', styles: {} },
                { type: 'paragraph', content: 'Dear {{first_name}},\n\nThank you for joining us. We are thrilled to have you as part of our organization.', styles: {} },
                { type: 'button', content: '', styles: { text: 'Get Started', url: '#', bg: '#2E7D32', color: '#ffffff' } },
                { type: 'spacer', content: '', styles: { height: '20px' } },
                { type: 'paragraph', content: 'If you have any questions, please don\'t hesitate to reach out.', styles: {} }
            ],
            newsletter: [
                { type: 'heading', content: 'Monthly Newsletter', styles: {} },
                { type: 'image', content: '', styles: { url: 'https://via.placeholder.com/600x200/2E7D32/ffffff?text=Newsletter', alt: 'Newsletter' } },
                { type: 'paragraph', content: 'Here\'s what\'s new this month...', styles: {} },
                { type: 'divider', content: '', styles: {} },
                { type: 'paragraph', content: 'Thank you for your continued support!', styles: {} }
            ],
            event: [
                { type: 'heading', content: 'You\'re Invited!', styles: {} },
                { type: 'paragraph', content: 'Dear {{first_name}},\n\nWe would love to invite you to our upcoming event.', styles: {} },
                { type: 'button', content: '', styles: { text: 'RSVP Now', url: '#', bg: '#1565C0', color: '#ffffff' } },
                { type: 'spacer', content: '', styles: { height: '30px' } },
                { type: 'paragraph', content: 'We look forward to seeing you there!', styles: {} }
            ]
        };
        
        if (templates[templateName]) {
            this.blocks = templates[templateName].map(b => ({ ...b, id: 'block-' + Date.now() + Math.random() }));
            this.renderBlocks();
            this.renderPreviewHtml();
            this.options.onChange(this.getBlocks());
        }
    }
}
