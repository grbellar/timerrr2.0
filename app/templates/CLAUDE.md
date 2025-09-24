# Design System Documentation for timerrr Templates

This file documents the design system and HTML structure used in the timerrr application templates to ensure consistency across all pages.

## Core Design Principles
- **Mobile-first responsive design** - All layouts start from mobile and enhance for larger screens
- **Minimal, clean aesthetic** - White cards on gray-50 background
- **Compact sizing** - Smaller fonts and tighter spacing for a refined look
- **Inter font family** - Loaded from Google Fonts via CDN

## Technology Stack
- **Tailwind CSS** via CDN (not compiled)
- **Responsive breakpoints**: `sm:` (640px+), `md:` (768px+), `lg:` (1024px+)
- **Jinja2 templating** with base.html inheritance
- **Vanilla JavaScript** for interactive elements (no framework)

## Template Files Overview

### base.html - Master Layout Template
The foundation template that all pages extend. Contains:
- HTML boilerplate with Tailwind CDN setup
- Responsive navigation header with mobile hamburger menu
- Content area defined by `{% block content %}`
- Mobile menu toggle JavaScript

### index.html - Landing Page
Simple placeholder page that extends base.html. Currently just displays "Hello!" text.

### timer.html - Time Tracking Interface
Active timer display for tracking work sessions:
- **Timer card** showing client name, running status indicator, elapsed time
- **Description input** for task details
- **Clock out button** to stop tracking
- Live timer display format: `0:00:11`

### entries.html - Time Entries Management
List view of all time entries with filtering:
- **Filter bar** with date range inputs, client dropdown, and apply button
- **Entry cards** showing client, description, duration, start/end times
- **Action buttons** for edit/delete on each entry
- **Status indicators** (green dot for running timers)

## HTML Structure Patterns

### Page Layout Template
```html
{% extends "base.html" %}
{% block title %}Page Name - timerrr{% endblock %}
{% block content %}
<div class="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
    <!-- Page content here -->
</div>
{% endblock %}
```

### Page Header Pattern
```html
<div class="mb-5 sm:mb-6">
    <h1 class="text-xl sm:text-2xl font-semibold mb-1">Page Title</h1>
    <p class="text-sm text-gray-600">Descriptive subtitle text</p>
</div>
```

### Card Container Pattern
```html
<div class="bg-white rounded-lg shadow-sm border border-gray-200 p-4 sm:p-5">
    <!-- Card content -->
</div>
```

### Mobile-Responsive Flex Layout
```html
<!-- Stack vertically on mobile, horizontal on desktop -->
<div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
    <div>Left content</div>
    <div>Right content</div>
</div>
```

### Form Input Pattern
```html
<input type="text"
       placeholder="Placeholder text"
       class="px-2.5 py-1.5 border border-gray-300 rounded-md text-sm
              focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
```

### Button Patterns

#### Primary Action Button (Red for Clock Out)
```html
<button class="w-full sm:w-auto bg-red-600 hover:bg-red-700 text-white
               px-4 sm:px-5 py-2 rounded-lg font-medium transition-colors text-sm">
    Clock out
</button>
```

#### Secondary Action Button (Dark)
```html
<button class="px-4 py-1.5 bg-gray-900 hover:bg-gray-800 text-white
               rounded-md font-medium transition-colors text-sm">
    Apply
</button>
```

#### Text Action Links
```html
<button class="text-blue-600 hover:text-blue-700 text-xs sm:text-sm font-medium">Edit</button>
<button class="text-red-600 hover:text-red-700 text-xs sm:text-sm font-medium">Delete</button>
```

### Status Indicator Pattern
```html
<div class="flex items-center gap-1.5">
    <div class="w-2 h-2 bg-green-500 rounded-full"></div>
    <span class="text-xs text-gray-500">timer running</span>
</div>
```

## Navigation Structure

### Desktop Navigation (Hidden on Mobile)
```html
<nav class="hidden md:flex items-center space-x-5 lg:space-x-6">
    <a href="/timer" class="text-sm text-gray-600 hover:text-gray-900 transition-colors">Timer</a>
    <a href="/entries" class="text-sm text-gray-600 hover:text-gray-900 transition-colors">Entries</a>
    <!-- Additional links -->
</nav>
```

### Mobile Navigation (Collapsible Menu)
```html
<!-- Hamburger Button -->
<button id="mobile-menu-btn" class="md:hidden p-2 rounded-md text-gray-600 hover:text-gray-900">
    <!-- SVG icons for menu/close states -->
</button>

<!-- Mobile Menu (Initially Hidden) -->
<nav id="mobile-menu" class="hidden md:hidden pb-3">
    <div class="flex flex-col space-y-2 pt-2">
        <a href="/timer" class="text-sm text-gray-600 hover:text-gray-900 px-3 py-2
                                rounded-md hover:bg-gray-100 transition-colors">Timer</a>
        <!-- Additional links -->
    </div>
</nav>
```

## Typography Scale

### Headings
- **Page title**: `text-xl sm:text-2xl font-semibold`
- **Subtitle**: `text-sm text-gray-600`
- **Card headers**: `text-base font-medium text-gray-700`
- **Timer display**: `text-2xl sm:text-3xl font-semibold`

### Body Text
- **Default**: `text-sm`
- **Small/Meta**: `text-xs`
- **Labels**: `text-xs sm:text-sm text-gray-500`

### Font Weights
- **Regular**: `font-normal` (400)
- **Medium**: `font-medium` (500)
- **Semibold**: `font-semibold` (600)

## Color Palette

### Backgrounds
- **Page background**: `bg-gray-50`
- **Card background**: `bg-white`
- **Input background**: `bg-gray-50` (for disabled/readonly)

### Borders
- **Card borders**: `border-gray-200`
- **Input borders**: `border-gray-300`
- **Dividers**: `border-b border-gray-200`

### Text Colors
- **Primary text**: `text-gray-900`
- **Secondary text**: `text-gray-700`
- **Muted text**: `text-gray-600`
- **Disabled text**: `text-gray-500`
- **Placeholder**: `text-gray-400`

### Interactive Colors
- **Primary CTA (Red)**: `bg-red-600 hover:bg-red-700`
- **Secondary (Dark)**: `bg-gray-900 hover:bg-gray-800`
- **Success (Green dot)**: `bg-green-500`
- **Links (Blue)**: `text-blue-600 hover:text-blue-700`
- **Danger (Red text)**: `text-red-600 hover:text-red-700`
- **Focus rings**: `focus:ring-2 focus:ring-blue-500`

## Spacing System

### Container Padding
- **Mobile**: `px-4 py-6`
- **Desktop**: `sm:px-6 sm:py-10`
- **Card padding**: `p-4 sm:p-5`

### Margins
- **Page title**: `mb-5 sm:mb-6`
- **Section spacing**: `mb-4 sm:mb-5`
- **Element spacing**: `mb-1` to `mb-3`

### Flex Gaps
- **Tight**: `gap-1.5` or `gap-2`
- **Normal**: `gap-3`
- **Wide**: `gap-5`

## Responsive Design Patterns

### Mobile-First Approach
Always start with mobile styles, then add desktop overrides:
```html
<!-- Mobile: full width, Desktop: auto width -->
<button class="w-full sm:w-auto">Button</button>

<!-- Mobile: stack, Desktop: row -->
<div class="flex flex-col sm:flex-row">Content</div>

<!-- Mobile: smaller text, Desktop: larger -->
<h1 class="text-xl sm:text-2xl">Heading</h1>
```

### Breakpoint Usage
- **No prefix**: Mobile and up (default)
- **sm:**: 640px and up (tablets)
- **md:**: 768px and up (small laptops)
- **lg:**: 1024px and up (desktops)

### Common Responsive Patterns
1. **Full width on mobile, auto on desktop**: `w-full sm:w-auto`
2. **Stack on mobile, row on desktop**: `flex-col sm:flex-row`
3. **Hide on mobile**: `hidden sm:block`
4. **Hide on desktop**: `sm:hidden`
5. **Responsive text**: `text-xs sm:text-sm`
6. **Responsive padding**: `p-4 sm:p-5`

## Interactive JavaScript

### Mobile Menu Toggle
Located in base.html, handles hamburger menu:
```javascript
const mobileMenuBtn = document.getElementById('mobile-menu-btn');
const mobileMenu = document.getElementById('mobile-menu');
const menuIcon = document.getElementById('menu-icon');
const closeIcon = document.getElementById('close-icon');

mobileMenuBtn.addEventListener('click', () => {
    mobileMenu.classList.toggle('hidden');
    menuIcon.classList.toggle('hidden');
    closeIcon.classList.toggle('hidden');
});
```

## Best Practices

### When Creating New Templates
1. **Always extend base.html** using `{% extends "base.html" %}`
2. **Use the standard page container** with `max-w-6xl mx-auto`
3. **Include page title section** with title and description
4. **Wrap content in white cards** with standard border and shadow
5. **Test on mobile first** - ensure all content is accessible on small screens
6. **Use semantic HTML** where appropriate (header, nav, main, etc.)

### Consistency Guidelines
1. **Typography**: Stick to the defined text size scale
2. **Spacing**: Use consistent padding/margin values
3. **Colors**: Only use colors from the defined palette
4. **Buttons**: Match existing button styles for similar actions
5. **Forms**: Keep input styles consistent across pages
6. **Icons**: Maintain consistent icon sizes (w-4 h-4 for small, w-6 h-6 for nav)

### Performance Considerations
1. **Tailwind via CDN**: Be aware of the full Tailwind CSS file size
2. **No JavaScript frameworks**: Keep interactions simple with vanilla JS
3. **Minimize custom CSS**: Use Tailwind utilities exclusively
4. **Optimize images**: Use appropriate formats and sizes when added

### Accessibility
1. **Focus states**: All interactive elements have focus rings
2. **Hover states**: Clear visual feedback on hover
3. **Mobile touch targets**: Buttons are large enough for touch (min 44px)
4. **Color contrast**: Text colors meet WCAG standards against backgrounds
5. **Semantic markup**: Use appropriate HTML elements for their purpose

## Common Component Recipes

### Empty State
```html
<div class="text-center py-12">
    <p class="text-gray-500 text-sm">No entries found</p>
</div>
```

### Loading State
```html
<div class="flex justify-center py-8">
    <div class="text-gray-500 text-sm">Loading...</div>
</div>
```

### Alert/Message
```html
<div class="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
    <p class="text-sm text-blue-700">Information message here</p>
</div>
```

### Data Table Row
```html
<div class="p-4 sm:p-5 border-b border-gray-200 hover:bg-gray-50 transition-colors">
    <!-- Row content -->
</div>
```

### Modal Dialog
Modals follow the same design principles with a semi-transparent overlay and centered white card:

```html
<!-- Modal Container -->
<div id="modal-id" class="fixed inset-0 bg-gray-900 bg-opacity-50 hidden items-center justify-center z-50" style="display: none;">
    <div class="bg-white rounded-lg shadow-xl border border-gray-200 w-full max-w-md mx-4">
        <!-- Modal Header -->
        <div class="px-5 py-4 border-b border-gray-200">
            <div class="flex items-center justify-between">
                <h2 class="text-lg font-semibold text-gray-900">Modal Title</h2>
                <button onclick="closeModal()" class="text-gray-400 hover:text-gray-600 transition-colors">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                </button>
            </div>
        </div>

        <!-- Modal Body -->
        <form id="modal-form" class="px-5 py-4">
            <!-- Form fields here -->
            <div class="mb-4">
                <label for="field-id" class="block text-sm font-medium text-gray-700 mb-1.5">Field Label</label>
                <input type="text" id="field-id"
                    class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm
                           focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500">
            </div>
        </form>

        <!-- Modal Footer -->
        <div class="px-5 py-4 border-t border-gray-200 flex items-center justify-end gap-3">
            <button onclick="closeModal()"
                class="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-900 transition-colors">
                Cancel
            </button>
            <button onclick="saveModal()"
                class="px-4 py-2 bg-gray-900 hover:bg-gray-800 text-white text-sm font-medium rounded-md transition-colors">
                Save Changes
            </button>
        </div>
    </div>
</div>
```

#### Modal JavaScript Pattern
```javascript
// Open modal
function openModal() {
    const modal = document.getElementById('modal-id');
    modal.style.display = 'flex';
    modal.classList.remove('hidden');
}

// Close modal
function closeModal() {
    const modal = document.getElementById('modal-id');
    modal.style.display = 'none';
    modal.classList.add('hidden');
}

// Close modal on Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeModal();
    }
});

// Close modal on background click
document.getElementById('modal-id').addEventListener('click', function(e) {
    if (e.target === this) {
        closeModal();
    }
});
```

#### Modal Design Specifications
- **Overlay**: `bg-gray-900 bg-opacity-50` - Semi-transparent dark overlay
- **Container**: `fixed inset-0` with `z-50` for highest z-index
- **Card**: White background with `rounded-lg shadow-xl border border-gray-200`
- **Max width**: `max-w-md` (28rem) for forms, adjust as needed
- **Mobile margin**: `mx-4` for edge spacing on mobile
- **Header**: `px-5 py-4` padding with bottom border
- **Body**: `px-5 py-4` padding for form content
- **Footer**: `px-5 py-4` padding with top border, right-aligned buttons
- **Close button**: X icon in top-right, `text-gray-400 hover:text-gray-600`
- **Form fields**: Standard form input styling with proper spacing
- **Button spacing**: `gap-3` between footer buttons
- **Animations**: Use `transition-colors` for hover states

This design system prioritizes clarity, consistency, and mobile usability while maintaining a professional, minimalist aesthetic suitable for a time tracking application.