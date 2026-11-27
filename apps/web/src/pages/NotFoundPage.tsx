import {Link} from "react-router";

export default function NotFoundPage() {
    return (
        <section className="container-narrow">
            <div className="card state-card">
                <div className="state-icon">🧭</div>
                <h2>Page not found</h2>
                <p>This page does not exist.</p>
                <Link to="/" className="btn">
                    ← Go to search
                </Link>
            </div>
        </section>
    );
}
