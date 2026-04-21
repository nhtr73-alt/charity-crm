// Rich Text Email Builder - WYSIWYG Editor
class RichEmailBuilder {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            onChange: options.onChange || (() => {}),
            mergeFields: options.mergeFields || ['first_name', 'last_name', 'email', 'company']
        };
        
        this.init();
    }
    
    init() {
        this.render();
    }
    
    render() {
        this.container.innerHTML = `
            <div class="rich-editor-container">
                <div class="rich-toolbar">
                    <div class="toolbar-group">
                        <select onchange="richEditor.format('fontFamily', this.value); this.value='';" title="Font">
                            <option value="">Font</option>
                            <option value="Arial, sans-serif">Arial</option>
                            <option value="'Times New Roman', serif">Times New Roman</option>
                            <option value="'Courier New', monospace">Courier</option>
                            <option value="Georgia, serif">Georgia</option>
                            <option value="Verdana, sans-serif">Verdana</option>
                        </select>
                        <select onchange="richEditor.format('fontSize', this.value + 'px'); this.value='';" title="Size">
                            <option value="">Size</option>
                            <option value="10">10px</option>
                            <option value="12">12px</option>
                            <option value="14">14px</option>
                            <option value="16">16px</option>
                            <option value="18">18px</option>
                            <option value="20">20px</option>
                            <option value="24">24px</option>
                            <option value="28">28px</option>
                            <option value="32">32px</option>
                            <option value="36">36px</option>
                        </select>
                        <select onchange="richEditor.format('foreColor', this.value); this.value='';" title="Text Color">
                            <option value="">Color</option>
                            <option value="#000000">Black</option>
                            <option value="#FFFFFF">White</option>
                            <option value="#FF0000">Red</option>
                            <option value="#00FF00">Green</option>
                            <option value="#0000FF">Blue</option>
                            <option value="#FFFF00">Yellow</option>
                            <option value="#FFA500">Orange</option>
                            <option value="#800080">Purple</option>
                            <option value="#2E7D32">Primary Green</option>
                            <option value="#1565C0">Primary Blue</option>
                        </select>
                        <select onchange="richEditor.format('backColor', this.value); this.value='';" title="Highlight">
                            <option value="">Highlight</option>
                            <option value="#FFFF00">Yellow</option>
                            <option value="#00FF00">Green</option>
                            <option value="#FFA500">Orange</option>
                            <option value="#FF0000">Red</option>
                            <option value="#0000FF">Blue</option>
                            <option value="transparent">None</option>
                        </select>
                    </div>
                    <div class="toolbar-group">
                        <button type="button" onclick="richEditor.format('bold')" title="Bold (Ctrl+B)">
                            <strong>B</strong>
                        </button>
                        <button type="button" onclick="richEditor.format('italic')" title="Italic (Ctrl+I)">
                            <em>I</em>
                        </button>
                        <button type="button" onclick="richEditor.format('underline')" title="Underline (Ctrl+U)">
                            <span style="text-decoration:underline">U</span>
                        </button>
                        <button type="button" onclick="richEditor.format('strikeThrough')" title="Strikethrough">
                            <span style="text-decoration:line-through">S</span>
                        </button>
                    </div>
                    <div class="toolbar-group">
                        <button type="button" onclick="richEditor.format('justifyLeft')" title="Align Left">
                            &#8676;
                        </button>
                        <button type="button" onclick="richEditor.format('justifyCenter')" title="Align Center">
                            &#8596;
                        </button>
                        <button type="button" onclick="richEditor.format('justifyRight')" title="Align Right">
                            &#8677;
                        </button>
                    </div>
                    <div class="toolbar-group">
                        <button type="button" onclick="richEditor.format('insertUnorderedList')" title="Bullet List">
                            &#8226;
                        </button>
                        <button type="button" onclick="richEditor.format('insertOrderedList')" title="Numbered List">
                            1.
                        </button>
                    </div>
                    <div class="toolbar-group">
                        <button type="button" onclick="richEditor.format('indent')" title="Indent">
                            &#8594;
                        </button>
                        <button type="button" onclick="richEditor.format('outdent')" title="Outdent">
                            &#8592;
                        </button>
                    </div>
                    <div class="toolbar-group">
                        <button type="button" onclick="richEditor.insertLink()" title="Insert Link">
                            &#128279;
                        </button>
                        <button type="button" onclick="richEditor.insertImage()" title="Insert Image">
                            &#128247;
                        </button>
                        <button type="button" onclick="richEditor.insertDivider()" title="Horizontal Line">
                            &#8212;
                        </button>
                    </div>
                    <div class="toolbar-group">
                        <button type="button" onclick="richEditor.undo()" title="Undo">
                            &#8630;
                        </button>
                        <button type="button" onclick="richEditor.redo()" title="Redo">
                            &#8631;
                        </button>
                    </div>
                    <div class="toolbar-group merge-fields">
                        <span class="me-2">Insert:</span>
                        <button type="button" class="btn btn-sm btn-outline-info" onclick="richEditor.insertMergeField('{{first_name}}')" title="First Name">First</button>
                        <button type="button" class="btn btn-sm btn-outline-info" onclick="richEditor.insertMergeField('{{last_name}}')" title="Last Name">Last</button>
                        <button type="button" class="btn btn-sm btn-outline-info" onclick="richEditor.insertMergeField('{{email}}')" title="Email">Email</button>
                        <button type="button" class="btn btn-sm btn-outline-info" onclick="richEditor.insertMergeField('{{company}}')" title="Company">Company</button>
                    </div>
                </div>
                <div class="rich-editor-canvas" id="editor-canvas" contenteditable="true">
                    <h1 style="color: #2E7D32; text-align: center;">Your Email Title Here</h1>
                    <p>Start typing your message here...</p>
                    <p><br></p>
                </div>
            </div>
        `;
        
        this.canvas = this.container.querySelector('#editor-canvas');
        
        this.canvas.addEventListener('input', () => {
            this.options.onChange(this.getHtml());
        });
        
        this.canvas.addEventListener('keydown', (e) => {
            if (e.ctrlKey && e.key === 'b') {
                e.preventDefault();
                this.format('bold');
            }
            if (e.ctrlKey && e.key === 'i') {
                e.preventDefault();
                this.format('italic');
            }
            if (e.ctrlKey && e.key === 'u') {
                e.preventDefault();
                this.format('underline');
            }
        });
    }
    
    format(command, value = null) {
        document.execCommand(command, false, value);
        this.canvas.focus();
        this.options.onChange(this.getHtml());
    }
    
    insertLink() {
        const url = prompt('Enter URL:');
        if (url) {
            this.format('createLink', url);
        }
    }
    
    insertImage() {
        const url = prompt('Enter image URL:');
        if (url) {
            this.format('insertImage', url);
        }
    }
    
    insertDivider() {
        this.format('insertHTML', '<hr>');
    }
    
    insertMergeField(field) {
        this.format('insertText', field);
    }
    
    undo() {
        this.format('undo');
    }
    
    redo() {
        this.format('redo');
    }
    
    getHtml() {
        return this.canvas.innerHTML;
    }
    
    setHtml(html) {
        this.canvas.innerHTML = html;
    }
    
    getText() {
        return this.canvas.innerText;
    }
    
    clear() {
        this.canvas.innerHTML = '<p><br></p>';
    }
    
    loadTemplate(templateName) {
        const templates = {
            welcome: `
                <h1 style="color: #2E7D32; text-align: center;">Welcome to Our Community!</h1>
                <p>Dear {{first_name}},</p>
                <p>Thank you for joining us. We are thrilled to have you as part of our organization.</p>
                <p style="text-align: center;">
                    <a href="#" style="display: inline-block; padding: 12px 24px; background: #2E7D32; color: #ffffff; text-decoration: none; border-radius: 4px; font-weight: bold;">Get Started</a>
                </p>
                <p>If you have any questions, please don't hesitate to reach out.</p>
                <p>Warm regards,<br><strong>The Team</strong></p>
            `,
            newsletter: `
                <h1 style="color: #2E7D32; text-align: center;">Monthly Newsletter</h1>
                <p><img src="https://via.placeholder.com/600x200/2E7D32/ffffff?text=Newsletter" alt="Newsletter" style="max-width: 100%;"></p>
                <h2>What's New This Month</h2>
                <p>Here's what's happening in our community...</p>
                <ul>
                    <li>Update 1</li>
                    <li>Update 2</li>
                    <li>Update 3</li>
                </ul>
                <hr>
                <p style="text-align: center;">Thank you for your continued support!</p>
            `,
            event: `
                <h1 style="color: #1565C0; text-align: center;">You're Invited!</h1>
                <p>Dear {{first_name}},</p>
                <p>We would love to invite you to our upcoming event.</p>
                <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; text-align: center;">
                    <h2>Event Name</h2>
                    <p><strong>Date:</strong> TBD</p>
                    <p><strong>Time:</strong> TBD</p>
                    <p><strong>Location:</strong> TBD</p>
                </div>
                <p style="text-align: center;">
                    <a href="#" style="display: inline-block; padding: 12px 24px; background: #1565C0; color: #ffffff; text-decoration: none; border-radius: 4px; font-weight: bold;">RSVP Now</a>
                </p>
                <p>We look forward to seeing you there!</p>
            `,
            thankyou: `
                <h1 style="color: #2E7D32; text-align: center;">Thank You!</h1>
                <p>Dear {{first_name}},</p>
                <p>Thank you for your generous support. Your contribution makes a real difference.</p>
                <p>With gratitude,<br><strong>The Team</strong></p>
            `
        };
        
        if (templates[templateName]) {
            this.canvas.innerHTML = templates[templateName];
            this.options.onChange(this.getHtml());
        }
    }
    
    exportHtml() {
        const content = this.getHtml();
        return this.wrapInEmailTemplate(content);
    }
    
    wrapInEmailTemplate(content) {
        return `<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 20px; background-color: #f5f5f5; font-family: Arial, sans-serif;">
    <table width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 8px; overflow: hidden;">
        <tr>
            <td style="padding: 30px;">
                ${content}
            </td>
        </tr>
    </table>
</body>
</html>`;
    }
    
    preview() {
        const html = this.exportHtml();
        const win = window.open('', '_blank');
        win.document.write(html);
        win.document.close();
    }
}

let richEditor;

document.addEventListener('DOMContentLoaded', function() {
    richEditor = new RichEmailBuilder('rich-editor', {
        onChange: function(html) {
            console.log('Content changed');
        },
        mergeFields: ['first_name', 'last_name', 'email', 'company']
    });
});

function insertMergeField(field) {
    richEditor.insertMergeField(field);
}
