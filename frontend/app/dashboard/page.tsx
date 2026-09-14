"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import {
  ArrowUpRight,
  CalendarDays,
  ChevronDown,
  Clock3,
  FileText,
  Instagram,
  LayoutDashboard,
  Loader2,
  Menu,
  MoreHorizontal,
  Plus,
  Search,
  Settings,
  Sparkles,
  Users,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";

import {
  DashboardOverview,
  DashboardReviewPost,
  DashboardUpcomingPost,
  getDashboardOverview,
} from "../../lib/api";

import {
  clearAccessToken,
  getAccessToken,
} from "../../lib/auth";

const navigation = [
  {
    label: "Overview",
    icon: LayoutDashboard,
    active: true,
  },
  {
    label: "Content",
    icon: FileText,
    active: false,
  },
  {
    label: "Campaigns",
    icon: Sparkles,
    active: false,
  },
  {
    label: "Calendar",
    icon: CalendarDays,
    active: false,
  },
];

function getDisplayName(email: string): string {
  const localPart =
    email.split("@")[0] || email;

  return localPart
    .replace(/[._-]+/g, " ")
    .split(" ")
    .filter(Boolean)
    .map(
      (part) =>
        part.charAt(0).toUpperCase() +
        part.slice(1).toLowerCase(),
    )
    .join(" ");
}

function getInitial(email: string): string {
  const name = getDisplayName(email);

  return (
    name.charAt(0).toUpperCase() ||
    "?"
  );
}

function formatDateTime(value: string | null): string {
  if (!value) {
    return "Not scheduled";
  }

  return new Intl.DateTimeFormat(
    "en-IN",
    {
      day: "numeric",
      month: "short",
      hour: "numeric",
      minute: "2-digit",
    },
  ).format(new Date(value));
}

function formatRelativeTime(value: string): string {
  const created =
    new Date(value).getTime();

  const now = Date.now();

  const difference = Math.max(
    0,
    now - created,
  );

  const minutes = Math.floor(
    difference / 60000,
  );

  if (minutes < 1) {
    return "Just now";
  }

  if (minutes < 60) {
    return `${minutes}m ago`;
  }

  const hours = Math.floor(
    minutes / 60,
  );

  if (hours < 24) {
    return `${hours}h ago`;
  }

  const days = Math.floor(
    hours / 24,
  );

  return `${days}d ago`;
}

function platformLabel(platform: string): string {
  if (platform === "instagram") {
    return "Instagram";
  }

  if (platform === "mastodon") {
    return "Mastodon";
  }

  return (
    platform.charAt(0).toUpperCase() +
    platform.slice(1)
  );
}

function getPlatformIcon(platform: string) {
  if (platform === "instagram") {
    return Instagram;
  }

  return Sparkles;
}

export default function DashboardPage() {
  const [
    mobileMenuOpen,
    setMobileMenuOpen,
  ] = useState(false);

  const [
    dashboard,
    setDashboard,
  ] = useState<DashboardOverview | null>(
    null,
  );

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadDashboard() {
      const token =
        getAccessToken();

      if (!token) {
        window.location.href =
          "/login";

        return;
      }

      try {
        setLoading(true);
        setError("");

        const overview =
          await getDashboardOverview(
            token,
          );

        if (cancelled) {
          return;
        }

        setDashboard(overview);
      } catch (err) {
        if (cancelled) {
          return;
        }

        const status =
          err &&
          typeof err === "object" &&
          "status" in err
            ? (
                err as {
                  status?: number;
                }
              ).status
            : undefined;

        if (status === 401) {
          clearAccessToken();

          window.location.href =
            "/login";

          return;
        }

        setError(
          err instanceof Error
            ? err.message
            : "Unable to load your workspace.",
        );
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadDashboard();

    return () => {
      cancelled = true;
    };
  }, []);

  const user =
    dashboard?.user ?? null;

  const displayName = user
    ? getDisplayName(user.email)
    : "";

  const initial = user
    ? getInitial(user.email)
    : "?";

  const primaryBrand =
    dashboard?.workspace.name ||
    "Workspace";

  const brandCount =
    dashboard?.workspace.brand_count ||
    0;

  const stats =
    dashboard?.stats ?? {
      drafts: 0,
      needs_review: 0,
      scheduled: 0,
      published: 0,
    };

  const upcomingPosts =
    dashboard?.upcoming ?? [];

  const reviewPosts =
    dashboard?.needs_review ?? [];

  const reviewPost:
    | DashboardReviewPost
    | null =
    reviewPosts.length > 0
      ? reviewPosts[0]
      : null;

  const connectedAccounts =
    dashboard?.connected_accounts ?? 0;

  if (loading) {
    return (
      <main className="dashboard-loading">
        <div className="dashboard-loading-orbit">
          <div />
          <Sparkles size={24} />
        </div>

        <p className="section-kicker">
          SOCIALPILOT
        </p>

        <h1>
          Preparing your workspace.
        </h1>

        <p>
          Loading your workspace
          overview.
        </p>

        <Loader2
          className="dashboard-loading-spinner"
          size={17}
        />
      </main>
    );
  }

  if (error || !dashboard) {
    return (
      <main className="dashboard-loading">
        <div className="dashboard-error-icon">
          !
        </div>

        <p className="section-kicker">
          WORKSPACE ERROR
        </p>

        <h1>
          We couldn&apos;t load this
          workspace.
        </h1>

        <p>
          {error ||
            "Unable to load your workspace."}
        </p>

        <button
          className="primary-button"
          onClick={() =>
            window.location.reload()
          }
        >
          Try again
          <ArrowUpRight size={16} />
        </button>
      </main>
    );
  }

  return (
    <main className="dashboard-shell">
      <aside
        className={`dashboard-sidebar ${
          mobileMenuOpen
            ? "open"
            : ""
        }`}
      >
        <div className="sidebar-top">
          <a
            href="/dashboard"
            className="brand"
          >
            <span className="brand-mark">
              <span />
            </span>

            <span>
              socialpilot
            </span>
          </a>

          <button
            className="sidebar-close mobile-only"
            onClick={() =>
              setMobileMenuOpen(
                false,
              )
            }
            aria-label="Close navigation"
          >
            <X size={19} />
          </button>
        </div>

        <div className="workspace-switcher">
          <div className="workspace-avatar">
            {primaryBrand
              .charAt(0)
              .toUpperCase()}
          </div>

          <div>
            <strong>
              {primaryBrand}
            </strong>

            <span>
              {brandCount === 1
                ? "Workspace"
                : `${brandCount} brands`}
            </span>
          </div>

          <ChevronDown size={15} />
        </div>

        <nav className="dashboard-nav">
          <p>WORKSPACE</p>

          {navigation.map(
            (item) => {
              const Icon =
                item.icon;

              return (
                <Link
                  key={
                    item.label
                  }
                  href={
                    item.label === "Content"
                      ? "/content"
                      : item.label === "Campaigns"
                        ? "/campaigns"
                        : item.label === "Calendar"
                          ? "/content?filter=scheduled"
                          : "/dashboard"
                  }
                  className={
                    item.active
                      ? "active"
                      : ""
                  }
                  onClick={() =>
                    setMobileMenuOpen(
                      false,
                    )
                  }
                >
                  <Icon size={17} />

                  <span>
                    {item.label}
                  </span>
                </Link>
              );
            },
          )}

          <p className="nav-spacer">
            MANAGE
          </p>

          <Link href="/accounts" onClick={() => setMobileMenuOpen(false)}>
            <Users size={17} />

            <span>
              Accounts
            </span>
          </Link>

          <Link href="/settings" onClick={() => setMobileMenuOpen(false)}>
            <Settings size={17} />

            <span>
              Settings
            </span>
          </Link>
        </nav>

        <div className="sidebar-bottom">
          <div className="sidebar-status">
            <span className="status-dot" />

            <span>
              {connectedAccounts >
              0
                ? `${
                    connectedAccounts
                  } connected account${
                    connectedAccounts ===
                    1
                      ? ""
                      : "s"
                  }`
                : "No accounts connected"}
            </span>
          </div>

          <div className="user-profile">
            <div className="user-avatar">
              {initial}
            </div>

            <div>
              <strong>
                {displayName ||
                  "User"}
              </strong>

              <span>
                {user?.email ?? ""}
              </span>
            </div>

            <MoreHorizontal
              size={17}
            />
          </div>
        </div>
      </aside>

      {mobileMenuOpen && (
        <button
          className="mobile-overlay mobile-only"
          onClick={() =>
            setMobileMenuOpen(
              false,
            )
          }
          aria-label="Close navigation"
        />
      )}

      <section className="dashboard-main">
        <header className="dashboard-header">
          <button
            className="menu-button mobile-only"
            onClick={() =>
              setMobileMenuOpen(
                true,
              )
            }
            aria-label="Open navigation"
          >
            <Menu size={21} />
          </button>

          <div className="breadcrumb">
            <span>
              Workspace
            </span>

            <span>/</span>

            <strong>
              Overview
            </strong>
          </div>

          <div className="dashboard-header-actions">
            <button
              className="icon-button"
              aria-label="Search"
            >
              <Search size={18} />
            </button>

            <button className="dashboard-create">
              <Plus size={16} />
              Create
            </button>
          </div>
        </header>

        <div className="dashboard-content">
          <motion.div
            className="dashboard-heading"
            initial={{
              opacity: 0,
              y: 16,
            }}
            animate={{
              opacity: 1,
              y: 0,
            }}
            transition={{
              duration: 0.55,
            }}
          >
            <div>
              <p className="section-kicker">
                OVERVIEW
              </p>

              <h1>
                Good morning,
                <br />

                <em>
                  {displayName ||
                    "there"}
                  .
                </em>
              </h1>
            </div>

            <p className="dashboard-intro">
              Your workspace at a glance.
              <br />
              Here&apos;s what needs your
              attention.
            </p>
          </motion.div>

          <section className="stats-grid">
            <StatCard
              label="Drafts"
              value={stats.drafts}
              description={`${brandCount} ${
                brandCount === 1
                  ? "brand"
                  : "brands"
              }`}
              delay={0.05}
            />

            <StatCard
              label="Needs review"
              value={
                stats.needs_review
              }
              description={
                stats.needs_review >
                0
                  ? "Waiting for approval"
                  : "Nothing waiting"
              }
              accent
              delay={0.1}
            />

            <StatCard
              label="Scheduled"
              value={
                stats.scheduled
              }
              description="Currently scheduled"
              delay={0.15}
            />

            <StatCard
              label="Published"
              value={
                stats.published
              }
              description="Published posts"
              delay={0.2}
            />
          </section>

          <section className="dashboard-grid">
            <motion.div
              className="dashboard-panel upcoming-panel"
              initial={{
                opacity: 0,
                y: 20,
              }}
              animate={{
                opacity: 1,
                y: 0,
              }}
              transition={{
                delay: 0.2,
              }}
            >
              <div className="panel-heading">
                <div>
                  <p className="section-kicker">
                    NEXT UP
                  </p>

                  <h2>
                    Upcoming content
                  </h2>
                </div>

                <button className="panel-link">
                  View calendar
                  <ArrowUpRight
                    size={14}
                  />
                </button>
              </div>

              <div className="upcoming-list">
                {upcomingPosts.length ===
                0 ? (
                  <EmptyState
                    title="Nothing scheduled yet."
                    description="Your scheduled posts will appear here."
                  />
                ) : (
                  upcomingPosts.map(
                    (
                      post,
                      index,
                    ) => {
                      const Icon =
                        getPlatformIcon(
                          post.platform,
                        );

                      return (
                        <motion.article
                          key={
                            post.id
                          }
                          className="upcoming-item"
                          initial={{
                            opacity: 0,
                            x: -8,
                          }}
                          animate={{
                            opacity: 1,
                            x: 0,
                          }}
                          transition={{
                            delay:
                              0.25 +
                              index *
                                0.07,
                          }}
                        >
                          <div className="platform-icon">
                            <Icon
                              size={16}
                            />
                          </div>

                          <div className="upcoming-info">
                            <strong>
                              {post.content.slice(
                                0,
                                75,
                              )}
                              {post.content
                                .length >
                              75
                                ? "..."
                                : ""}
                            </strong>

                            <span>
                              {platformLabel(
                                post.platform,
                              )}
                            </span>
                          </div>

                          <div className="upcoming-time">
                            <span>
                              {formatDateTime(
                                post.scheduled_at,
                              )}
                            </span>

                            <small>
                              SCHEDULED
                            </small>
                          </div>
                        </motion.article>
                      );
                    },
                  )
                )}
              </div>
            </motion.div>

            <motion.div
              className="dashboard-panel review-panel"
              initial={{
                opacity: 0,
                y: 20,
              }}
              animate={{
                opacity: 1,
                y: 0,
              }}
              transition={{
                delay: 0.28,
              }}
            >
              <div className="panel-heading">
                <div>
                  <p className="section-kicker">
                    YOUR ATTENTION
                  </p>

                  <h2>
                    Needs review
                  </h2>
                </div>

                <span className="review-count">
                  {stats.needs_review}
                </span>
              </div>

              {reviewPost ? (
                <div className="review-card">
                  <div className="review-card-top">
                    <span className="ai-badge">
                      <Sparkles
                        size={13}
                      />

                      Awaiting approval
                    </span>

                    <button
                      aria-label="More options"
                    >
                      <MoreHorizontal
                        size={17}
                      />
                    </button>
                  </div>

                  <h3>
                    {reviewPost.content.slice(
                      0,
                      130,
                    )}

                    {reviewPost
                      .content
                      .length >
                    130
                      ? "..."
                      : ""}
                  </h3>

                  <p>
                    {reviewPost.campaign_name
                      ? `Campaign: ${reviewPost.campaign_name}`
                      : "This post is waiting for your decision."}
                  </p>

                  <div className="review-card-meta">
                    <span>
                      {(() => {
                        const Icon =
                          getPlatformIcon(
                            reviewPost.platform,
                          );

                        return (
                          <>
                            <Icon
                              size={14}
                            />

                            {platformLabel(
                              reviewPost.platform,
                            )}
                          </>
                        );
                      })()}
                    </span>

                    <span>
                      <Clock3
                        size={14}
                      />

                      Created{" "}
                      {formatRelativeTime(
                        reviewPost.created_at,
                      )}
                    </span>
                  </div>

                  <button className="review-button">
                    Review post

                    <ArrowUpRight
                      size={15}
                    />
                  </button>
                </div>
              ) : (
                <div className="review-empty">
                  <div className="review-empty-icon">
                    <Sparkles
                      size={19}
                    />
                  </div>

                  <h3>
                    You&apos;re all
                    caught up.
                  </h3>

                  <p>
                    No posts are
                    currently waiting
                    for human approval.
                  </p>
                </div>
              )}
            </motion.div>
          </section>
        </div>
      </section>
    </main>
  );
}

function StatCard({
  label,
  value,
  description,
  accent = false,
  delay = 0,
}: {
  label: string;
  value: number;
  description: string;
  accent?: boolean;
  delay?: number;
}) {
  return (
    <motion.article
      className={`stat-card ${
        accent
          ? "accent"
          : ""
      }`}
      initial={{
        opacity: 0,
        y: 14,
      }}
      animate={{
        opacity: 1,
        y: 0,
      }}
      transition={{
        delay,
        duration: 0.45,
      }}
    >
      <span>
        {label}
      </span>

      <strong>
        {value}
      </strong>

      <small>
        {description}
      </small>
    </motion.article>
  );
}

function EmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="dashboard-empty-state">
      <div>
        <CalendarDays size={18} />
      </div>

      <strong>
        {title}
      </strong>

      <span>
        {description}
      </span>
    </div>
  );
}