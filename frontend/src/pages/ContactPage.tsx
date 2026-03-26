import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { AlertCircle, CheckCircle, ArrowLeft, Mail, Send } from "lucide-react";
import { contactSales } from "../api/contact";

const contactSchema = z.object({
  name: z.string().min(2, "Name must be at least 2 characters"),
  email: z.string().email("Invalid email address"),
  company: z.string().optional(),
  message: z.string().min(10, "Message must be at least 10 characters"),
});

type ContactFormData = z.infer<typeof contactSchema>;

export default function ContactPage() {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);
  const [apiError, setApiError] = useState("");
  const [showSuccessModal, setShowSuccessModal] = useState(false);
  const [successMessage, setSuccessMessage] = useState("");

  const {
    register,
    handleSubmit,
    formState: { errors },
    reset,
  } = useForm<ContactFormData>({
    resolver: zodResolver(contactSchema),
  });

  const onSubmit = async (data: ContactFormData) => {
    setIsLoading(true);
    setApiError("");

    try {
      const response = await contactSales({
        name: data.name,
        email: data.email,
        company: data.company || "",
        message: data.message,
      });
      setSuccessMessage(response.message);
      setShowSuccessModal(true);
      reset();
    } catch (error) {
      setApiError(
        error instanceof Error ? error.message : "Failed to send inquiry",
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleSuccessClose = () => {
    setShowSuccessModal(false);
    navigate("/");
  };

  return (
    <div className="py-8 max-w-2xl mx-auto">
      {/* Header */}
      <div className="mb-10">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate("/")}
          className="mb-6 -ml-2 text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Home
        </Button>

        <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 border border-primary/20 mb-4">
          <Mail className="w-4 h-4 text-primary" />
          <span className="text-sm font-medium text-primary">Get in Touch</span>
        </div>

        <h1 className="text-3xl md:text-4xl font-bold text-foreground tracking-tight mb-3">
          Contact Sales
        </h1>
        <p className="text-muted-foreground text-lg font-light">
          Have questions about our Enterprise plan or need a custom solution?
          Get in touch with our sales team.
        </p>
      </div>

      {/* Contact Form */}
      <div className="rounded-2xl border border-border/50 bg-card/50 p-8">
        <form className="space-y-6" onSubmit={handleSubmit(onSubmit)}>
          {apiError && (
            <Alert
              variant="destructive"
              className="rounded-xl border-destructive/20 bg-destructive/5"
            >
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{apiError}</AlertDescription>
            </Alert>
          )}

          <div>
            <label
              htmlFor="name"
              className="block text-sm font-medium text-foreground mb-2"
            >
              Name <span className="text-destructive">*</span>
            </label>
            <input
              {...register("name")}
              type="text"
              placeholder="John Doe"
              className="block w-full px-4 py-3 rounded-xl border border-border/50 bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all duration-200"
            />
            {errors.name && (
              <p className="mt-2 text-sm text-destructive">
                {errors.name.message}
              </p>
            )}
          </div>

          <div>
            <label
              htmlFor="email"
              className="block text-sm font-medium text-foreground mb-2"
            >
              Email <span className="text-destructive">*</span>
            </label>
            <input
              {...register("email")}
              type="email"
              placeholder="john@example.com"
              className="block w-full px-4 py-3 rounded-xl border border-border/50 bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all duration-200"
            />
            {errors.email && (
              <p className="mt-2 text-sm text-destructive">
                {errors.email.message}
              </p>
            )}
          </div>

          <div>
            <label
              htmlFor="company"
              className="block text-sm font-medium text-foreground mb-2"
            >
              Company
            </label>
            <input
              {...register("company")}
              type="text"
              placeholder="Your Company"
              className="block w-full px-4 py-3 rounded-xl border border-border/50 bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all duration-200"
            />
          </div>

          <div>
            <label
              htmlFor="message"
              className="block text-sm font-medium text-foreground mb-2"
            >
              Message <span className="text-destructive">*</span>
            </label>
            <textarea
              {...register("message")}
              rows={6}
              placeholder="Tell us about your needs..."
              className="block w-full px-4 py-3 rounded-xl border border-border/50 bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 focus:border-primary transition-all duration-200 resize-none"
            />
            {errors.message && (
              <p className="mt-2 text-sm text-destructive">
                {errors.message.message}
              </p>
            )}
          </div>

          <div className="flex gap-3 pt-2">
            <Button
              type="submit"
              variant="gradient"
              disabled={isLoading}
              className="flex-1 h-12 rounded-xl font-semibold"
            >
              {isLoading ? (
                "Sending..."
              ) : (
                <>
                  <Send className="w-4 h-4 mr-2" />
                  Send Inquiry
                </>
              )}
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={() => navigate("/")}
              className="h-12 px-6 rounded-xl border-border/50 hover:bg-muted/50 hover:border-border transition-all duration-300"
            >
              Cancel
            </Button>
          </div>
        </form>
      </div>

      {/* Additional Info */}
      <div className="mt-8 text-center">
        <p className="text-muted-foreground">
          You can also email us directly at{" "}
          <a
            href="mailto:hello@goodgist.com"
            className="text-primary hover:text-primary/80 font-semibold transition-colors"
          >
            hello@goodgist.com
          </a>
        </p>
      </div>

      {/* Success Modal */}
      <Dialog open={showSuccessModal} onOpenChange={setShowSuccessModal}>
        <DialogContent className="rounded-2xl border-border/50 bg-card">
          <DialogHeader>
            <div className="flex items-center justify-center mb-4">
              <div className="p-4 rounded-2xl bg-emerald-500/10 border border-emerald-500/20">
                <CheckCircle className="h-8 w-8 text-emerald-500" />
              </div>
            </div>
            <DialogTitle className="text-center text-xl font-bold text-foreground">
              Inquiry Sent!
            </DialogTitle>
            <DialogDescription className="text-center text-muted-foreground">
              {successMessage}
            </DialogDescription>
          </DialogHeader>
          <div className="flex justify-center mt-4">
            <Button
              variant="gradient"
              onClick={handleSuccessClose}
              className="h-11 px-6 rounded-xl"
            >
              Back to Home
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Footer spacing */}
      <div className="h-12" />
    </div>
  );
}
