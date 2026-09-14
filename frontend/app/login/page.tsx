"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Eye,
  EyeOff,
  Loader2,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { FormEvent, useState } from "react";

import {
  ApiError,
  getCurrentUser,
  login,
} from "../../lib/api";

import { saveAccessToken } from "../../lib/auth";

type LoginStage =
  | "idle"
  | "authenticating"
  | "workspace";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [showPassword, setShowPassword] =
    useState(false);

  const [stage, setStage] =
    useState<LoginStage>("idle");

  const [error, setError] = useState("");

  const handleSubmit = async (
    event: FormEvent<HTMLFormElement>,
  ) => {
    event.preventDefault();

    setError("");
    setStage("authenticating");

    try {
      const result = await login(
        email.trim(),
        password,
      );

      saveAccessToken(result.access_token);

      await getCurrentUser(
        result.access_token,
      );

      setStage("workspace");

      window.setTimeout(() => {
        window.location.href = "/dashboard";
      }, 700);
    } catch (err) {
      setStage("idle");

      if (err instanceof ApiError) {
        if (err.status === 401) {
          setError(
            "The email or password you entered is incorrect.",
          );
        } else {
          setError(err.message);
        }
      } else {
        setError(
          "Unable to connect to SocialPilot. Please try again.",
        );
      }
    }
  };

  const loading =
    stage === "authenticating";

  return (
    <main className="login-page">
      <div className="login-background" />

      <header className="login-header">
        <Link href="/" className="brand">
          <span className="brand-mark">
            <span />
          </span>

          <span>socialpilot</span>
        </Link>

        <Link href="/" className="back-link">
          <ArrowLeft size={15} />
          Back to SocialPilot
        </Link>
      </header>

      <div className="login-layout">
        <section className="login-story">
          <motion.div
            initial={{
              opacity: 0,
              y: 18,
            }}
            animate={{
              opacity: 1,
              y: 0,
            }}
            transition={{
              duration: 0.65,
            }}
          >
            <p className="section-kicker">
              YOUR WORKSPACE
            </p>

            <h1>
              Your ideas.
              <br />
              <em>Your decisions.</em>
            </h1>

            <p className="login-story-copy">
              SocialPilot brings AI into the
              social workflow without handing
              over the final say.
            </p>

            <div className="login-principles">
              <div>
                <span className="login-principle-icon">
                  <Sparkles size={15} />
                </span>

                <div>
                  <strong>
                    AI-assisted
                  </strong>

                  <span>
                    Generate and refine content
                    faster.
                  </span>
                </div>
              </div>

              <div>
                <span className="login-principle-icon">
                  <ShieldCheck size={15} />
                </span>

                <div>
                  <strong>
                    Human controlled
                  </strong>

                  <span>
                    Nothing gets published without
                    approval.
                  </span>
                </div>
              </div>
            </div>
          </motion.div>
        </section>

        <motion.section
          className="login-card"
          initial={{
            opacity: 0,
            y: 25,
            scale: 0.98,
          }}
          animate={{
            opacity: 1,
            y: 0,
            scale: 1,
          }}
          transition={{
            duration: 0.7,
            delay: 0.08,
            ease: [0.22, 1, 0.36, 1],
          }}
        >
          <AnimatePresence mode="wait">
            {stage === "workspace" ? (
              <motion.div
                key="workspace"
                className="login-loading-state"
                initial={{
                  opacity: 0,
                }}
                animate={{
                  opacity: 1,
                }}
              >
                <div className="loading-orbit">
                  <div className="loading-orbit-ring" />

                  <div className="loading-core">
                    <Check size={24} />
                  </div>
                </div>

                <p className="loading-eyebrow">
                  AUTHENTICATED
                </p>

                <h2>
                  Preparing your workspace.
                </h2>

                <p>
                  Everything is ready. Taking
                  you to SocialPilot.
                </p>

                <div className="loading-progress">
                  <motion.span
                    initial={{
                      width: "0%",
                    }}
                    animate={{
                      width: "100%",
                    }}
                    transition={{
                      duration: 0.65,
                      ease: "easeInOut",
                    }}
                  />
                </div>
              </motion.div>
            ) : (
              <motion.div
                key="form"
                initial={{
                  opacity: 0,
                }}
                animate={{
                  opacity: 1,
                }}
              >
                <div className="login-card-heading">
                  <p className="section-kicker">
                    WELCOME BACK
                  </p>

                  <h2>
                    Sign in to
                    <br />
                    <em>
                      your workspace.
                    </em>
                  </h2>

                  <p>
                    Pick up where you left off.
                  </p>
                </div>

                <form
                  onSubmit={handleSubmit}
                  className="login-form"
                >
                  <label>
                    <span>Email</span>

                    <input
                      type="email"
                      value={email}
                      onChange={(event) =>
                        setEmail(
                          event.target.value,
                        )
                      }
                      placeholder="you@company.com"
                      autoComplete="email"
                      disabled={loading}
                      required
                    />
                  </label>

                  <label>
                    <span>Password</span>

                    <div className="password-field">
                      <input
                        type={
                          showPassword
                            ? "text"
                            : "password"
                        }
                        value={password}
                        onChange={(event) =>
                          setPassword(
                            event.target.value,
                          )
                        }
                        placeholder="Enter your password"
                        autoComplete="current-password"
                        disabled={loading}
                        required
                      />

                      <button
                        type="button"
                        className="password-toggle"
                        onClick={() =>
                          setShowPassword(
                            (value) =>
                              !value,
                          )
                        }
                        aria-label={
                          showPassword
                            ? "Hide password"
                            : "Show password"
                        }
                        disabled={loading}
                      >
                        {showPassword ? (
                          <EyeOff size={17} />
                        ) : (
                          <Eye size={17} />
                        )}
                      </button>
                    </div>
                  </label>

                  {error && (
                    <motion.div
                      className="login-error"
                      initial={{
                        opacity: 0,
                        y: -5,
                      }}
                      animate={{
                        opacity: 1,
                        y: 0,
                      }}
                    >
                      {error}
                    </motion.div>
                  )}

                  <button
                    type="submit"
                    className="primary-button login-submit"
                    disabled={loading}
                  >
                    {loading ? (
                      <>
                        <Loader2
                          className="button-spinner"
                          size={16}
                        />
                        Authenticating...
                      </>
                    ) : (
                      <>
                        Continue
                        <ArrowRight size={16} />
                      </>
                    )}
                  </button>
                </form>

                <div className="login-footer-note">
                  <span>
                    <ShieldCheck size={14} />
                    Secure workspace
                  </span>

                  <span>
                    Human approval required
                  </span>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.section>
      </div>

      <footer className="login-page-footer">
        <span>
          © 2026 SocialPilot AI
        </span>

        <span>
          Built with intention.
        </span>
      </footer>
    </main>
  );
}