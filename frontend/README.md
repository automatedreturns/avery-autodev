# Avery Frontend

React + TypeScript + Vite frontend application with user authentication, protected routes, and modern UI.

## Features

- **React 18** with TypeScript for type-safe development
- **Vite** for lightning-fast development and build
- **React Router** for client-side routing
- **Tailwind CSS** for modern, responsive styling
- **React Hook Form + Zod** for robust form validation
- **Axios** for API communication
- **JWT Authentication** with persistent sessions
- **Protected Routes** with automatic redirects
- **Context API** for global state management

## Project Structure

```
src/
├── api/
│   └── auth.ts              # API calls to backend
├── components/
│   ├── Navbar.tsx           # Navigation with auth state
│   ├── ProtectedRoute.tsx   # Route protection wrapper
│   └── LoadingSpinner.tsx   # Loading indicator
├── context/
│   └── AuthContext.tsx      # Authentication state & functions
├── pages/
│   ├── HomePage.tsx         # Landing page
│   ├── SignUpPage.tsx       # User registration
│   ├── SignInPage.tsx       # User login
│   ├── ProfilePage.tsx      # User profile (protected)
│   └── NotFoundPage.tsx     # 404 page
├── types/
│   └── auth.ts              # TypeScript interfaces
├── utils/
│   └── storage.ts           # localStorage helpers
├── App.tsx                  # Main app with routing
├── main.tsx                 # Entry point
└── index.css                # Tailwind imports
```

## Prerequisites

- Node.js 18+ and npm
- Backend server running on http://localhost:8000

## Installation

```bash
# Install dependencies
npm install
```

## Environment Variables

Create a `.env` file in the frontend directory:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Development

Start the development server:

```bash
npm run dev
```

The application will be available at http://localhost:5173

## Building for Production

```bash
# Create production build
npm run build

# Preview production build locally
npm run preview
```

## Features Guide

### Authentication

The app uses JWT-based authentication with the following flow:

1. **Sign Up**: Register a new account at `/signup`
   - Email validation (only @godgist.com domain allowed)
   - Password strength requirements (8+ chars, uppercase, lowercase, number, special char)
   - Confirm password matching
   - Auto-login after successful registration

2. **Sign In**: Login with credentials at `/signin`
   - Username and password validation
   - JWT token stored in localStorage (Remember Me)
   - Automatic redirect to profile page

3. **Profile**: View account information at `/profile` (protected route)
   - Display user details (username, email, account status, member since)
   - Logout functionality

### Protected Routes

Routes wrapped with `<ProtectedRoute>` require authentication:
- Unauthenticated users are redirected to `/signin`
- Loading spinner shown while checking auth status
- Session persists across browser refreshes

### Form Validation

All forms use React Hook Form with Zod schema validation:
- Real-time validation as user types
- Clear error messages below each field
- Submit button disabled during API calls
- API error messages displayed prominently

### Persistent Sessions

User sessions persist across browser refreshes:
- JWT token stored in localStorage
- Automatic authentication check on app load
- Token included in all API requests via interceptor
- Token cleared on logout or 401 errors

## API Integration

The frontend communicates with the FastAPI backend:

### Endpoints Used

- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/login` - User login
- `GET /api/v1/auth/me` - Get current user

### Error Handling

- Network errors: "Unable to connect to server"
- 401 Unauthorized: Clear token, redirect to login
- 400 Bad Request: Show specific validation errors
- Other errors: "An unexpected error occurred"

## Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Create production build
- `npm run preview` - Preview production build
- `npm run lint` - Run ESLint

## Tech Stack

- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool
- **React Router v6** - Routing
- **Tailwind CSS v4** - Styling (CSS-based configuration)
- **Axios** - HTTP client
- **React Hook Form** - Form management
- **Zod** - Schema validation
- **Context API** - State management

## Styling with Tailwind CSS v4

This project uses **Tailwind CSS v4**, which has a different configuration approach:

### Key Differences from v3
- **CSS-based configuration** instead of `tailwind.config.js`
- Configuration is done in `src/index.css` using `@theme` directive
- Uses `@import "tailwindcss"` instead of `@tailwind` directives
- PostCSS plugin: `@tailwindcss/postcss` instead of `tailwindcss`

### Configuration Files
- **src/index.css**: Main Tailwind import and theme configuration
- **postcss.config.js**: PostCSS configuration with `@tailwindcss/postcss`

### Customizing Theme (Optional)
To customize colors, spacing, or other theme values, edit `src/index.css`:

```css
@import "tailwindcss";

@theme {
  --color-primary: #3b82f6;
  --color-secondary: #64748b;
  --font-display: "Inter", sans-serif;
}
```

### Verify Tailwind is Working
After starting the dev server, check:
1. Inspect element in browser DevTools
2. Look for Tailwind utility classes in the HTML
3. CSS file should be ~17KB (contains all Tailwind styles)

If styles are missing:
```bash
# Rebuild the project
npm run build

# Clear cache and restart
rm -rf node_modules/.vite
npm run dev
```

## File Descriptions

### Core Files

- **src/App.tsx**: Main component with routing setup
- **src/main.tsx**: Application entry point
- **src/index.css**: Tailwind CSS imports

### Context

- **AuthContext.tsx**: Manages authentication state (user, token, isAuthenticated) and functions (login, signup, logout)

### API Layer

- **api/auth.ts**: Axios instance with interceptors, API functions for authentication

### Components

- **Navbar.tsx**: Navigation bar with conditional rendering based on auth state
- **ProtectedRoute.tsx**: Higher-order component for route protection
- **LoadingSpinner.tsx**: Reusable loading indicator

### Pages

- **HomePage.tsx**: Landing page with features overview
- **SignUpPage.tsx**: Registration form with validation
- **SignInPage.tsx**: Login form with validation
- **ProfilePage.tsx**: User profile display (protected)
- **NotFoundPage.tsx**: 404 error page

### Utils

- **storage.ts**: localStorage helpers for token management

### Types

- **auth.ts**: TypeScript interfaces for User, SignUpData, SignInData, AuthResponse, AuthContextType

## Password Requirements

- Minimum 8 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character

## Security Notes

- JWT tokens stored in localStorage
- Tokens automatically included in API requests
- Tokens cleared on logout or authentication errors
- All forms include CSRF protection via token-based auth
- No sensitive data stored in frontend code

## Styling

The app uses Tailwind CSS with:
- Responsive design (mobile-first)
- Color scheme: Blue primary, Red danger, Green success
- Consistent spacing and typography
- Hover and focus states for accessibility
- Loading and disabled states for forms

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)

## Troubleshooting

### "Unable to connect to server"
- Ensure backend is running on http://localhost:8000
- Check VITE_API_BASE_URL in .env file

### "401 Unauthorized" errors
- Token may be expired or invalid
- Try logging out and logging back in

### Blank page after login
- Check browser console for errors
- Verify profile route is properly protected
- Ensure user data is being fetched correctly

## Development Tips

- Use React DevTools for component inspection
- Use Redux DevTools for state debugging
- Check Network tab for API call issues
- Use ESLint for code quality
- Test in multiple browsers

## License

This project is open source and available under the MIT License.
