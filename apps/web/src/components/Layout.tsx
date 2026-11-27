import {useEffect, useState} from "react";
import {Link, Outlet} from "react-router";

export default function Layout() {
    const [showTop, setShowTop] = useState(false);

    // The "back to top" button shows once the page has scrolled down a bit (small screens).
    useEffect(() => {
        function onScroll() {
            setShowTop(window.scrollY > 400);
        }
        onScroll();
        window.addEventListener("scroll", onScroll, {passive: true});
        return () => window.removeEventListener("scroll", onScroll);
    }, []);

    return (
        <div className="app">
            <header className="navbar">
                <Link to="/" className="navbar-brand" aria-label="SmartHelix home">
                    <span className="brand-icon" aria-hidden="true">
                        <HelixIcon />
                    </span>
                    <span>
                        <span className="brand-smart">Smart</span>
                        <span className="brand-helix">Helix</span>
                    </span>
                </Link>
                <span className="navbar-tagline">SMEs, startups and freelancers in one search</span>
            </header>

            <main className="app-main">
                <Outlet />
            </main>

            <button
                type="button"
                className={`scroll-to-top${showTop ? " visible" : ""}`}
                onClick={() => window.scrollTo({top: 0, behavior: "smooth"})}
                aria-label="Back to top"
                tabIndex={showTop ? 0 : -1}
            >
                <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 19V5M5 12l7-7 7 7" />
                </svg>
            </button>
        </div>
    );
}

function HelixIcon() {
    return (
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
            <path d="M7 2C7 8 17 8 17 12S7 16 7 22" />
            <path d="M17 2C17 8 7 8 7 12S17 16 17 22" />
            <path d="M9 5.5h6M9 18.5h6" opacity="0.6" />
        </svg>
    );
}
