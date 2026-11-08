"use client";

import Link from "next/link";
import Image from "next/image";
import { motion } from "framer-motion";
import {
  MessageCircle,
  ListTodo,
  CalendarDays,
  Home,
  ClipboardCheck,
  TrendingUp,
  ArrowRight,
} from "lucide-react";
import CloudBackground from "@/components/CloudBackground";

const FEATURES = [
  {
    icon: MessageCircle,
    title: "AI academic assistant",
    desc: "Ask about your classes, faculty hours, and study plan after you sign in.",
  },
  {
    icon: ListTodo,
    title: "Task manager",
    desc: "Track assignments, revisions, and attendance reminders in one list.",
  },
  {
    icon: CalendarDays,
    title: "Academic calendar",
    desc: "CAT dates, holidays, tasks, and approved leave on a single calendar.",
  },
  {
    icon: Home,
    title: "Hostel leave",
    desc: "Apply for hostel leave from this app — no paper slip for routine requests.",
  },
  {
    icon: ClipboardCheck,
    title: "Attendance & marks",
    desc: "Live grades and attendance from the institute database, explained in plain language.",
  },
  {
    icon: TrendingUp,
    title: "Forecasting",
    desc: "See if you can miss a class and still stay above 75%, plus predicted internals.",
  },
];

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-[#FFFFFF] font-sans overflow-x-hidden relative">
      <CloudBackground variant="hero" />

      <nav className="fixed top-0 left-0 right-0 z-50 bg-white/90 backdrop-blur-md border-b border-[#7C5AED]/10">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Image
              src="/kare-logo.png"
              alt="Kalasalingam Academy of Research and Education"
              width={48}
              height={48}
              className="object-contain"
            />
            <div>
              <span className="font-bold text-lg text-primary block">Campus-GPT</span>
              <span className="text-xs text-gray-500">Kalasalingam Academy of Research and Education</span>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/register" className="text-gray-600 hover:text-primary text-sm font-medium">
              Register
            </Link>
            <Link
              href="/login"
              className="px-5 py-2.5 rounded-xl bg-primary text-white font-semibold hover:bg-primary-dark transition-all shadow-lg shadow-primary/25"
            >
              Login
            </Link>
          </div>
        </div>
      </nav>

      <section className="pt-32 pb-16 px-6 relative z-10">
        <div className="max-w-4xl mx-auto text-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-primary/10 text-primary text-sm font-medium mb-6"
          >
            <MessageCircle className="w-4 h-4" />
            Institute workspace for students and faculty
          </motion.div>
          <motion.h1
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-5xl md:text-6xl font-bold text-primary mb-6 leading-tight"
          >
            Your AI-powered university companion.
          </motion.h1>
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-xl text-gray-600 mb-10 max-w-2xl mx-auto"
          >
            Ask anything about your university after you sign in. Role-aware, privacy-aware, and grounded in official sources — not a generic chatbot.
          </motion.p>
          <Link
            href="/login"
            className="inline-flex items-center justify-center gap-2 px-8 py-4 rounded-xl bg-primary text-white font-semibold text-lg hover:bg-primary-dark shadow-xl shadow-primary/30"
          >
            Ask anything about your university...
            <ArrowRight className="w-5 h-5" />
          </Link>
        </div>
      </section>

      <section className="py-16 px-6 relative z-10">
        <div className="max-w-6xl mx-auto">
          <h2 className="text-3xl font-bold text-center text-primary mb-3">What you can use</h2>
          <p className="text-center text-gray-500 text-sm mb-12">
            Features available inside your workspace after login. Personal records are never shown here.
          </p>
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {FEATURES.map((f, i) => (
              <motion.div
                key={f.title}
                initial={{ opacity: 0, y: 16 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.06 }}
                className="p-6 rounded-2xl bg-white border border-[#7C5AED]/15"
              >
                <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center mb-4">
                  <f.icon className="w-6 h-6 text-primary" />
                </div>
                <h3 className="font-semibold text-lg text-primary mb-2">{f.title}</h3>
                <p className="text-gray-600 text-sm">{f.desc}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      <footer className="py-8 border-t border-[#7C5AED]/10 relative z-10">
        <div className="max-w-6xl mx-auto px-6 text-center text-gray-500 text-sm">
          Campus-GPT — Kalasalingam Academy of Research and Education
        </div>
      </footer>
    </div>
  );
}
