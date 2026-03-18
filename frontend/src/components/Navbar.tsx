import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { ThemeSwitcher } from "./ThemeSwitcher";
import { Logo } from "./Logo";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";
import { LogOut, ChevronDown, LayoutGrid, User, Menu, X } from "lucide-react";

const Navbar = () => {
  const { isAuthenticated, user, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const menuItems = [
    { path: '/workspaces', label: 'Workspaces', icon: LayoutGrid },
    { path: '/profile', label: 'Profile', icon: User },
  ];

  return (
    <>
      <nav className="fixed top-0 left-0 right-0 z-50 p-2.5 w-full bg-card/95 backdrop-blur-sm border-b border-border/50">
        <div className="w-full mx-auto px-4 sm:px-6 lg:px-8 h-full">
          <div className="flex items-center justify-between h-full">
            {/* Logo */}
            <Link to="/" className="flex-shrink-0 hover:opacity-80 transition-opacity">
              <Logo size="md" showText={true} />
            </Link>

            {/* Desktop Navigation */}
            <div className="hidden sm:flex items-center gap-2">
              {isAuthenticated ? (
                <>
                  <ThemeSwitcher />
                  <Separator orientation="vertical" className="h-5 mx-1" />
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <button className="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-accent transition-colors min-h-[44px]">
                        <Avatar className="h-7 w-7">
                          <AvatarFallback className="bg-primary text-primary-foreground text-xs font-semibold">
                            {user?.username?.charAt(0).toUpperCase() || "U"}
                          </AvatarFallback>
                        </Avatar>
                        <span className="hidden sm:block text-sm font-medium text-foreground max-w-[100px] truncate">
                          {user?.username}
                        </span>
                        <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                      </button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end" className="w-48">
                      {menuItems.map((item) => (
                        <DropdownMenuItem key={item.path} asChild>
                          <Link to={item.path} className="cursor-pointer">
                            <item.icon className="mr-2 h-4 w-4" />
                            {item.label}
                          </Link>
                        </DropdownMenuItem>
                      ))}
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        onClick={logout}
                        className="text-destructive focus:text-destructive cursor-pointer"
                      >
                        <LogOut className="mr-2 h-4 w-4" />
                        Sign out
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </>
              ) : (
                <>
                  <ThemeSwitcher />
                  <Button variant="ghost" size="sm" asChild className="min-h-[44px]">
                    <Link to="/signin">Sign in</Link>
                  </Button>
                  <Button size="sm" asChild className="min-h-[44px]">
                    <Link to="/signup">Get Started</Link>
                  </Button>
                </>
              )}
            </div>

            {/* Mobile Menu Button */}
            <Button
              variant="ghost"
              size="icon"
              className="sm:hidden h-10 w-10 min-h-[44px] min-w-[44px]"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
            >
              {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
            </Button>
          </div>
        </div>

        {/* Mobile Menu Dropdown */}
        {mobileMenuOpen && (
          <div className="sm:hidden border-t border-border bg-card animate-in slide-in-from-top-2 duration-200">
            <div className="px-4 py-4 space-y-2">
              {isAuthenticated ? (
                <>
                  {/* User Info */}
                  <div className="flex items-center gap-3 px-2 py-3 border-b border-border mb-2">
                    <Avatar className="h-10 w-10">
                      <AvatarFallback className="bg-primary text-primary-foreground font-semibold">
                        {user?.username?.charAt(0).toUpperCase() || "U"}
                      </AvatarFallback>
                    </Avatar>
                    <div>
                      <p className="font-medium text-foreground">{user?.username}</p>
                      <p className="text-xs text-muted-foreground">{user?.email}</p>
                    </div>
                  </div>

                  {/* Nav Links */}
                  {menuItems.map((item) => (
                    <Link
                      key={item.path}
                      to={item.path}
                      onClick={() => setMobileMenuOpen(false)}
                      className="flex items-center gap-3 w-full px-4 py-3 min-h-[48px] text-left text-base font-medium text-foreground hover:bg-muted rounded-lg transition-colors"
                    >
                      <item.icon className="h-5 w-5 text-muted-foreground" />
                      {item.label}
                    </Link>
                  ))}

                  {/* Theme & Logout */}
                  <div className="flex items-center justify-between px-4 py-3 border-t border-border mt-2">
                    <span className="text-sm text-muted-foreground">Theme</span>
                    <ThemeSwitcher />
                  </div>

                  <button
                    onClick={() => {
                      logout();
                      setMobileMenuOpen(false);
                    }}
                    className="flex items-center gap-3 w-full px-4 py-3 min-h-[48px] text-left text-base font-medium text-destructive hover:bg-destructive/10 rounded-lg transition-colors"
                  >
                    <LogOut className="h-5 w-5" />
                    Sign out
                  </button>
                </>
              ) : (
                <>
                  <div className="flex items-center justify-between px-4 py-3 border-t border-border">
                    <span className="text-sm text-muted-foreground">Theme</span>
                    <ThemeSwitcher />
                  </div>

                  <div className="pt-2 space-y-2">
                    <Button
                      variant="outline"
                      className="w-full min-h-[48px]"
                      asChild
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      <Link to="/signin">Sign in</Link>
                    </Button>
                    <Button
                      variant="gradient"
                      className="w-full min-h-[48px]"
                      asChild
                      onClick={() => setMobileMenuOpen(false)}
                    >
                      <Link to="/signup">Get Started</Link>
                    </Button>
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </nav>
    </>
  );
};

export default Navbar;
