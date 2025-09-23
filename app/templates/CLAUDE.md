# Design System Documentation for timerrr

This file documents the design system used in the timerrr application templates to ensure consistency across all pages.

## Core Design Principles
- **Mobile-first responsive design** - All layouts start from mobile and enhance for larger screens
- **Minimal, clean aesthetic** - White cards on gray-50 background
- **Compact sizing** - Smaller fonts and tighter spacing for a refined look
- **Inter font family** - Loaded from Google Fonts

## Technology Stack
- **Tailwind CSS** via CDN (not compiled)
- **Responsive breakpoints**: `sm:` (640px+), `md:` (768px+), `lg:` (1024px+)
- **Jinja2 templating** with base.html inheritance

## Layout Structure

### Base Template (`base.html`)
All pages extend this template using `{% extends "base.html" %}`.

#### Header Specifications
```html
<header class="bg-white border-b border-gray-200">
  <div class="max-w-6xl mx-auto px-4 sm:px-6">
    <div class="flex items-center justify-between h-14">
```
- Height: `h-14` (56px)
- Logo: `text-lg font-semibold`
- Desktop nav links: `text-sm text-gray-600 hover:text-gray-900`
- Nav spacing: `space-x-5 lg:space-x-6`

#### Mobile Navigation
- Hamburger menu button: `md:hidden` (hidden on desktop)
- Mobile menu: Vertical stack with `text-sm` links
- Toggle functionality via JavaScript (show/hide menu and swap icons)

### Page Container Pattern
```html
<div class="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
```
- Max width: `max-w-6xl`
- Mobile padding: `px-4 py-6`
- Desktop padding: `sm:px-6 sm:py-10`

## Typography Scale

### Headings
- Page title: `text-xl sm:text-2xl font-semibold`
- Subtitle/description: `text-sm text-gray-600`
- Card headers: `text-sm sm:text-base font-medium`

### Body Text
- Default: `text-sm`
- Small/secondary: `text-xs`
- Labels: `text-xs sm:text-sm text-gray-500`

### Spacing
- Page title margin: `mb-5 sm:mb-6`
- Section margins: `mb-4 sm:mb-5`
- Internal spacing: `gap-3` or `gap-5` for flex containers

## Card Design Pattern

### Basic Card
```html
<div class="bg-white rounded-lg shadow-sm border border-gray-200 p-5 sm:p-6">
```
- Background: `bg-white`
- Border: `border border-gray-200`
- Shadow: `shadow-sm`
- Padding: `p-4 sm:p-5` (compact) or `p-5 sm:p-6` (normal)
- Corner radius: `rounded-lg`

### Interactive Elements
- Hover state for cards: `hover:bg-gray-50 transition-colors`
- Focus states: `focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500`

## Form Elements

### Input Fields
```html
<input type="text" class="px-2.5 py-1.5 border border-gray-300 rounded-md
       focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm">
```
- Padding: `px-2.5 py-1.5`
- Border: `border-gray-300`
- Text size: `text-sm`

### Buttons

#### Primary Button (Green)
```html
<button class="bg-green-600 hover:bg-green-700 text-white px-4 sm:px-5 py-2.5
               rounded-lg font-medium transition-colors text-sm">
```

#### Secondary Button (Dark)
```html
<button class="bg-gray-900 hover:bg-gray-800 text-white px-4 py-1.5
               rounded-md font-medium transition-colors text-sm">
```

#### Text Buttons (Actions)
- Edit: `text-blue-600 hover:text-blue-700 text-xs sm:text-sm font-medium`
- Delete: `text-red-600 hover:text-red-700 text-xs sm:text-sm font-medium`

### Responsive Button Pattern
Mobile: `w-full` (full width)
Desktop: `sm:w-auto` (auto width)

## Icon Sizing
- Small icons (calendars, etc.): `w-4 h-4`
- Navigation hamburger: `w-6 h-6`

## Color Palette
- **Background**: `bg-gray-50` (body), `bg-white` (cards)
- **Borders**: `border-gray-200` (cards), `border-gray-300` (inputs)
- **Text**:
  - Primary: `text-gray-900`
  - Secondary: `text-gray-600`
  - Muted: `text-gray-500`
- **Interactive**:
  - Green CTA: `bg-green-600 hover:bg-green-700`
  - Dark buttons: `bg-gray-900 hover:bg-gray-800`
  - Links: `text-blue-600 hover:text-blue-700`
  - Danger: `text-red-600 hover:text-red-700`

## Responsive Patterns

### Mobile-First Stacking
```html
<!-- Stack on mobile, horizontal on desktop -->
<div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
```

### Responsive Text Sizing
- Mobile → Desktop progression:
  - `text-xs sm:text-sm` (small text)
  - `text-sm sm:text-base` (normal text)
  - `text-xl sm:text-2xl` (headings)
  - `text-3xl sm:text-4xl` (large displays)

### Responsive Spacing
- Padding: `p-4 sm:p-5` or `p-5 sm:p-6`
- Margins: `mb-5 sm:mb-6`
- Gaps: `gap-3` (mobile) to `gap-5` (desktop)

## Creating New Pages

### Template Structure
```html
{% extends "base.html" %}

{% block title %}Page Name - timerrr{% endblock %}

{% block content %}
<div class="max-w-6xl mx-auto px-4 sm:px-6 py-6 sm:py-10">
    <!-- Page Title -->
    <div class="mb-5 sm:mb-6">
        <h1 class="text-xl sm:text-2xl font-semibold">Page Title</h1>
        <p class="text-sm text-gray-600">Optional description</p>
    </div>

    <!-- Card Content -->
    <div class="bg-white rounded-lg shadow-sm border border-gray-200 p-5 sm:p-6">
        <!-- Content here -->
    </div>
</div>
{% endblock %}
```

## Important Notes
1. **Always use mobile-first responsive classes** - Start with mobile styles, add `sm:` prefixes for larger screens
2. **Maintain consistent spacing** - Use the established padding/margin scale
3. **Keep text sizes compact** - Default to `text-sm` for body text
4. **Test responsive behavior** - Ensure hamburger menu works on mobile
5. **Preserve hover states** - Include transition-colors for smooth interactions
6. **Follow the card pattern** - White background, gray border, subtle shadow

This design system prioritizes clarity, consistency, and mobile usability while maintaining a professional, minimalist aesthetic.