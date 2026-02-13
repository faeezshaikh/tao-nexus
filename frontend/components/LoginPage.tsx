"use client";

import { useState, FormEvent } from "react";
import { authenticate } from "../lib/auth";
import { useAuth } from "../contexts/AuthContext";

export default function LoginPage() {
    const [username, setUsername] = useState("");
    const [password, setPassword] = useState("");
    const [error, setError] = useState("");
    const [isLoading, setIsLoading] = useState(false);
    const { login } = useAuth();

    const handleSubmit = async (e: FormEvent) => {
        e.preventDefault();
        setError("");
        setIsLoading(true);

        // Simulate a slight delay for better UX
        await new Promise((resolve) => setTimeout(resolve, 500));

        const user = authenticate(username, password);

        if (user) {
            login(user);
        } else {
            setError("Invalid username or password");
            setIsLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-[#FAFAFA] text-[#0A0A0A] flex items-center justify-center p-4 relative overflow-hidden">
            {/* Decorative background elements */}
            <div className="fixed top-10 right-10 w-32 h-32 bg-[#FFE500] rounded-full opacity-20 blur-3xl pointer-events-none" />
            <div className="fixed bottom-20 left-10 w-40 h-40 bg-[#FF6B9D] rounded-full opacity-20 blur-3xl pointer-events-none" />
            <div className="fixed top-1/2 left-1/3 w-36 h-36 bg-[#00D4FF] rounded-full opacity-15 blur-3xl pointer-events-none" />

            <div className="w-full max-w-md relative z-10">
                {/* Header */}
                <div className="mb-8 text-center">
                    <div className="flex items-center justify-center gap-4 mb-4">
                        <img
                            src="/lens-icon.png"
                            alt="TAO Lens"
                            className="w-14 h-14 md:w-16 md:h-16 border-4 border-[#0A0A0A] shadow-[4px_4px_0px_#0A0A0A] bg-white p-2 transform -rotate-6"
                        />
                        <h1 className="text-5xl md:text-6xl font-bold tracking-tight">
                            <span className="inline-block bg-[#FFE500] px-4 py-2 border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] transform -rotate-1">
                                TAO
                            </span>
                            <span className="inline-block ml-3 bg-[#00D4FF] px-4 py-2 border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] transform rotate-1">
                                LENS
                            </span>
                        </h1>
                    </div>
                    <p className="text-lg font-medium mt-6">
                        Ask natural-language questions about your AWS costs
                    </p>
                    <p className="text-sm text-[#0A0A0A]/70 mt-2">
                        Powered by AWS MCP Server & AI-Driven Analytics
                    </p>
                </div>

                {/* Login Card */}
                <div className="bg-white border-4 border-[#0A0A0A] shadow-[12px_12px_0px_#0A0A0A] p-8">
                    <div className="mb-6">
                        <h2 className="text-2xl font-bold uppercase tracking-wide inline-block bg-[#00FF94] px-3 py-1 border-2 border-[#0A0A0A]">
                            🔐 Login
                        </h2>
                    </div>

                    <form onSubmit={handleSubmit} className="space-y-5">
                        {/* Username Field */}
                        <div>
                            <label className="block text-sm font-bold mb-2 uppercase tracking-wide">
                                Username
                            </label>
                            <input
                                type="text"
                                value={username}
                                onChange={(e) => setUsername(e.target.value)}
                                className="w-full border-4 border-[#0A0A0A] px-4 py-3 text-base font-medium focus:outline-none focus:shadow-[6px_6px_0px_#0A0A0A] focus:-translate-y-1 transition-all bg-[#FAFAFA]"
                                placeholder="Enter your username"
                                required
                                disabled={isLoading}
                            />
                        </div>

                        {/* Password Field */}
                        <div>
                            <label className="block text-sm font-bold mb-2 uppercase tracking-wide">
                                Password
                            </label>
                            <input
                                type="password"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                                className="w-full border-4 border-[#0A0A0A] px-4 py-3 text-base font-medium focus:outline-none focus:shadow-[6px_6px_0px_#0A0A0A] focus:-translate-y-1 transition-all bg-[#FAFAFA]"
                                placeholder="Enter your password"
                                required
                                disabled={isLoading}
                            />
                        </div>

                        {/* Error Message */}
                        {error && (
                            <div className="bg-[#FF6B9D] border-4 border-[#0A0A0A] shadow-[4px_4px_0px_#0A0A0A] px-4 py-3 animate-shake">
                                <p className="font-bold text-sm">⚠️ {error}</p>
                            </div>
                        )}

                        {/* Login Button */}
                        <button
                            type="submit"
                            disabled={isLoading}
                            className="w-full bg-[#FFE500] border-4 border-[#0A0A0A] shadow-[6px_6px_0px_#0A0A0A] px-6 py-4 font-bold text-lg hover:shadow-[8px_8px_0px_#0A0A0A] hover:-translate-y-1 hover:translate-x-1 transition-all duration-200 disabled:bg-[#E0E0E0] disabled:cursor-not-allowed disabled:shadow-[4px_4px_0px_#0A0A0A] active:shadow-[4px_4px_0px_#0A0A0A] active:translate-y-0.5 active:-translate-x-0.5"
                        >
                            {isLoading ? "🔄 LOGGING IN..." : "🚀 LOGIN"}
                        </button>
                    </form>

                    {/* Demo Credentials Hint */}
                    {/* <div className="mt-6 pt-6 border-t-4 border-[#0A0A0A] border-dashed">
                        <p className="text-xs font-bold text-[#0A0A0A]/60 mb-2">
                            💡 DEMO CREDENTIALS:
                        </p>
                        <div className="space-y-1 text-xs font-medium text-[#0A0A0A]/70">
                            <p>• admin / admin123</p>
                            <p>• tao.user / tao2024</p>
                            <p>• demo / demo</p>
                        </div>
                    </div> */}
                </div>

                {/* Footer */}
                <div className="text-center mt-8">
                    <p className="text-sm font-medium text-[#0A0A0A]/60">
                        Built with ❤️ by the Tuning and Optimization (TAO) Team at Discount Tire
                    </p>
                </div>
            </div>

            <style jsx>{`
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          25% { transform: translateX(-4px); }
          75% { transform: translateX(4px); }
        }
        .animate-shake {
          animation: shake 0.3s ease-in-out;
        }
      `}</style>
        </div>
    );
}
