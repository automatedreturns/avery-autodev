interface LogoProps {
  size?: "sm" | "md" | "lg" | "xl";
  showText?: boolean;
  className?: string;
}

const sizeClasses = {
  sm: "w-8 h-8",
  md: "w-12 h-12",
  lg: "w-16 h-16",
  xl: "w-24 h-24",
};

const textSizeClasses = {
  sm: "text-lg",
  md: "text-xl",
  lg: "text-2xl",
  xl: "text-3xl",
};

export const Logo = ({
  size = "md",
  showText = true,
  className = "",
}: LogoProps) => {
  return (
    <div className={`flex items-center gap-3 ${className}`}>
      <img
        src="/Avery-Purple-Icon.png"
        alt="Avery Developer Logo"
        className={`${sizeClasses[size]} object-contain`}
      />
      {showText && (
        <span className={`font-bold text-foreground ${textSizeClasses[size]}`}>
          Avery Developer
        </span>
      )}
    </div>
  );
};
