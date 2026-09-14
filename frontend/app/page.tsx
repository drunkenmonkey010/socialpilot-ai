"use client";

import { motion, useReducedMotion } from "framer-motion";
import {
  ArrowDown,
  ArrowRight,
  Check,
  ChevronRight,
  Instagram,
  Menu,
  Sparkles,
  X,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";

const sections = [
  { id: "product", label: "What we do" },
  { id: "principles", label: "Our approach" },
  { id: "ambition", label: "Our ambition" },
  { id: "contact", label: "Contact" },
];

const workflow = [
  ["01", "Plan", "Turn campaigns and ideas into an organised content plan."],
  [
    "02",
    "Create",
    "Use AI to draft content that starts from your brief, not a blank page.",
  ],
  [
    "03",
    "Review",
    "Keep a human approval step between generation and publication.",
  ],
  [
    "04",
    "Publish",
    "Schedule and send approved content to connected platforms.",
  ],
];

export default function Home() {
  const [menuOpen, setMenuOpen] = useState(false);
  const reduceMotion = useReducedMotion();

  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({
      behavior: reduceMotion ? "auto" : "smooth",
    });

    setMenuOpen(false);
  };

  return (
    <main className="site-shell">
      <header className="nav-wrap">
        <nav className="nav" aria-label="Primary navigation">
          <button
            className="brand"
            onClick={() =>
              window.scrollTo({
                top: 0,
                behavior: reduceMotion ? "auto" : "smooth",
              })
            }
            aria-label="SocialPilot home"
          >
            <span className="brand-mark">
              <span />
            </span>
            <span>socialpilot</span>
          </button>

          <div className="nav-links desktop-only">
            {sections.map((section) => (
              <button
                key={section.id}
                onClick={() => scrollTo(section.id)}
              >
                {section.label}
              </button>
            ))}
          </div>

          <div className="nav-actions desktop-only">
            <Link href="/login" className="text-button">
              Sign in
            </Link>

            <Link href="/login" className="nav-cta">
              Get started
              <ArrowRight size={16} />
            </Link>
          </div>

          <button
            className="menu-button mobile-only"
            onClick={() => setMenuOpen((value) => !value)}
            aria-label={menuOpen ? "Close menu" : "Open menu"}
            aria-expanded={menuOpen}
          >
            {menuOpen ? <X size={21} /> : <Menu size={21} />}
          </button>
        </nav>

        <motion.div
          className="mobile-menu"
          initial={false}
          animate={{
            opacity: menuOpen ? 1 : 0,
            y: menuOpen ? 0 : -8,
            pointerEvents: menuOpen ? "auto" : "none",
          }}
          transition={{ duration: 0.2 }}
        >
          {sections.map((section) => (
            <button
              key={section.id}
              onClick={() => scrollTo(section.id)}
            >
              {section.label}
              <ArrowRight size={15} />
            </button>
          ))}

          <Link
            href="/login"
            className="mobile-login"
            onClick={() => setMenuOpen(false)}
          >
            Sign in
            <ArrowRight size={16} />
          </Link>
        </motion.div>
      </header>

      <section className="hero" aria-labelledby="hero-title">
        <div className="hero-grid" />
        <div className="hero-glow glow-one" />
        <div className="hero-glow glow-two" />

        <div className="hero-content">
          <motion.div
            className="eyebrow"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <span className="eyebrow-dot" />
            AI-assisted social media management
          </motion.div>

          <motion.h1
            id="hero-title"
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              duration: 0.8,
              delay: 0.08,
              ease: [0.22, 1, 0.36, 1],
            }}
          >
            Create less.
            <br />
            <em>Communicate more.</em>
          </motion.h1>

          <motion.p
            className="hero-copy"
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.65, delay: 0.18 }}
          >
            SocialPilot brings AI into the social workflow without taking the
            human out of it. Plan, create, review, schedule and publish from
            one considered workspace.
          </motion.p>

          <motion.div
            className="hero-actions"
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.28 }}
          >
            <Link href="/login" className="primary-button">
              Get started
              <ArrowRight size={17} />
            </Link>

            <button
              className="secondary-button"
              onClick={() => scrollTo("product")}
            >
              See how it works
              <ArrowDown size={16} />
            </button>
          </motion.div>
        </div>

        <motion.div
          className="hero-orbit"
          initial={{ opacity: 0, scale: 0.84 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{
            duration: 1.1,
            delay: 0.25,
            ease: [0.22, 1, 0.36, 1],
          }}
          aria-hidden="true"
        >
          <div className="orbit-ring ring-a" />
          <div className="orbit-ring ring-b" />

          <div className="orbit-core">
            <Sparkles size={27} strokeWidth={1.5} />
          </div>

          <div className="orbit-node node-a">
            <span>Draft</span>
            <strong>04</strong>
          </div>

          <div className="orbit-node node-b">
            <Instagram size={15} />
            <strong>Live</strong>
          </div>

          <div className="orbit-node node-c">
            <Check size={15} />
            <strong>Approved</strong>
          </div>
        </motion.div>

        <button
          className="scroll-cue"
          onClick={() => scrollTo("product")}
          aria-label="Scroll to learn more"
        >
          <span>Scroll to explore</span>
          <ArrowDown size={15} />
        </button>
      </section>

      <section id="product" className="section section-product">
        <Reveal>
          <p className="section-kicker">01 / WHAT WE DO</p>

          <h2>
            One workflow.
            <br />
            <span>From idea to publish.</span>
          </h2>

          <p className="section-intro">
            The busywork is handled by software. The decisions stay with you.
          </p>
        </Reveal>

        <div className="workflow">
          {workflow.map(([number, title, copy], index) => (
            <Reveal key={number} delay={index * 0.08}>
              <article className="workflow-item">
                <span className="workflow-number">{number}</span>

                <div>
                  <h3>{title}</h3>
                  <p>{copy}</p>
                </div>

                <ChevronRight
                  className="workflow-arrow"
                  size={19}
                />
              </article>
            </Reveal>
          ))}
        </div>
      </section>

      <section id="principles" className="section principles-section">
        <Reveal>
          <p className="section-kicker">02 / OUR APPROACH</p>
        </Reveal>

        <div className="principles-layout">
          <Reveal>
            <h2>
              AI should
              <br />
              <em>assist.</em>
              <br />
              Not disappear
              <br />
              behind the curtain.
            </h2>
          </Reveal>

          <Reveal delay={0.1}>
            <div className="principles-copy">
              <p>
                We are building SocialPilot around a simple boundary: AI can
                suggest, generate and accelerate. A person decides what gets
                published.
              </p>

              <p>
                That means the product is designed around visibility, review
                and control—not blind automation.
              </p>

              <div className="principle-line">
                <span />
                <b>Human-in-the-loop by design</b>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      <section id="ambition" className="section ambition-section">
        <div className="ambition-panel">
          <div className="ambition-noise" />

          <Reveal>
            <p className="section-kicker">03 / OUR AMBITION</p>
          </Reveal>

          <Reveal delay={0.08}>
            <h2>
              Make social media
              <br />
              <span>less operational.</span>
            </h2>
          </Reveal>

          <Reveal delay={0.16}>
            <p>
              We want teams to spend their time on ideas, relationships and
              decisions—not repetitive publishing tasks.
            </p>
          </Reveal>

          <Reveal delay={0.22}>
            <div className="ambition-statement">
              <span>SocialPilot</span>
              <strong>intelligence + intention</strong>
              <span>in the same workflow.</span>
            </div>
          </Reveal>
        </div>
      </section>

      <section id="contact" className="section contact-section">
        <Reveal>
          <p className="section-kicker">04 / CONTACT</p>

          <h2>
            Have an idea?
            <br />
            <em>Let&apos;s talk.</em>
          </h2>

          <a
            className="contact-link"
            href="mailto:hello@socialpilot.ai"
          >
            hello@socialpilot.ai
            <ArrowRight size={17} />
          </a>
        </Reveal>
      </section>

      <footer className="footer">
        <span>© 2026 SocialPilot AI</span>
        <span>Built with intention.</span>
      </footer>
    </main>
  );
}

function Reveal({
  children,
  delay = 0,
}: {
  children: React.ReactNode;
  delay?: number;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 28 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{
        duration: 0.65,
        delay,
        ease: [0.22, 1, 0.36, 1],
      }}
    >
      {children}
    </motion.div>
  );
}