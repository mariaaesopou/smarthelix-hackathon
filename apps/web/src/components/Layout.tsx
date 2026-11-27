import {NavLink, Outlet} from "react-router";

export default function Layout() {
    return (
        <div className="app">
            <header className="app-header">
                <NavLink to="/" className="brand"> SmartHelix </NavLink>
                <span className="tagline"> SMEs, startups and freelancers in one search</span>
            </header>
            <main className="app-main">
                <Outlet />
            </main>
        </div>
    );
}