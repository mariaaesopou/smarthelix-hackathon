import {Link, Outlet, useLocation, useParams} from "react-router";
import {TYPE_LABELS} from "../api";
import {TYPES, useProfileSearch} from "../hooks/profiles";
import {Meta, PillList, TypePill} from "../components/ui";

// Browse view: full-width search bar on top, listings on the left, the selected profile on the right.
export default function SearchPage() {
    const {q, type, result, error, loading, updateParams, handleSubmit} = useProfileSearch();
    const {search} = useLocation();
    const {id: openId} = useParams();

    return (
        <section className="browse-page">
            <div className="search-top">
                <header className="page-header">
                    <h1>Find the right partner</h1>
                    <p>Search SMEs, young entrepreneurs and freelancers by name, skill, service or region.</p>
                </header>

                <div className="card filters-card search-toolbar">
                    <form key={q} role="search" className="search-row" onSubmit={handleSubmit}>
                        <div className="search-input-wrap">
                            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" aria-hidden="true">
                                <circle cx="11" cy="11" r="7" />
                                <path d="m20 20-3.5-3.5" />
                            </svg>
                            <input
                                name="q"
                                className="search-input"
                                defaultValue={q}
                                placeholder="e.g. React developer, bakery, Attica…"
                                aria-label="Search profiles"
                            />
                        </div>
                        <button type="submit" className="btn">
                            Search
                        </button>
                    </form>

                    <div className="filters-second-row">
                        <span className="filter-label">Profile type</span>
                        <div className="toggle-group" role="group" aria-label="Filter by profile type">
                            <button
                                type="button"
                                className={`btn-toggle${type === undefined ? " active" : ""}`}
                                aria-pressed={type === undefined}
                                onClick={() => updateParams({q})}
                            >
                                All
                            </button>
                            {TYPES.map((t) => (
                                <button
                                    key={t}
                                    type="button"
                                    className={`btn-toggle${type === t ? " active" : ""}`}
                                    aria-pressed={type === t}
                                    onClick={() => updateParams({q, type: t})}
                                >
                                    {TYPE_LABELS[t]}
                                </button>
                            ))}
                        </div>
                    </div>

                    <p className="results-count" aria-live="polite">
                        {loading || !result ? "Searching…" : (
                            <>
                                <strong>{result.total}</strong> {result.total === 1 ? "profile" : "profiles"} found
                            </>
                        )}
                    </p>
                </div>
            </div>

            <div className="browse">
                <div className="browse-list">
                    {loading && <SkeletonList />}

                    {error && !loading && (
                        <div className="card state-card error" role="alert">
                            <div className="state-icon">⚠️</div>
                            <h2>Something went wrong</h2>
                            <p>{error}</p>
                        </div>
                    )}

                    {result && !loading && !error && (
                        <>
                            {result.items.length === 0 ? (
                                <div className="card state-card">
                                    <div className="state-icon">🔍</div>
                                    <h2>No profiles match your search</h2>
                                    <p>Try fewer words or a different profile type.</p>
                                    <button type="button" className="btn btn-outline" onClick={() => updateParams({})}>
                                        Clear search
                                    </button>
                                </div>
                            ) : (
                                <ul className="profile-list">
                                    {result.items.map((p, i) => {
                                        // Clicking the open listing again closes it.
                                        const isOpen = p.id === openId;
                                        return (
                                            <li key={p.id}>
                                                <Link
                                                    to={{pathname: isOpen ? "/" : `/profiles/${p.id}`, search}}
                                                    className={`card profile-card${isOpen ? " active" : ""}`}
                                                    aria-current={isOpen ? "page" : undefined}
                                                    title={isOpen ? "Click again to close this profile" : undefined}
                                                    style={{animationDelay: `${Math.min(i, 10) * 40}ms`}}
                                                >
                                                    <div className="profile-card-top">
                                                        <h2 className="profile-card-name">{p.name}</h2>
                                                        <TypePill type={p.type} />
                                                    </div>
                                                    <Meta sector={p.sector} region={p.region} />
                                                    <p className="profile-card-desc">{p.description}</p>
                                                    {p.skills.length > 0 && <PillList items={p.skills} max={4} />}
                                                    <div className="profile-card-footer">
                                                        <span>via {p.sources.join(", ")}</span>
                                                        <span className="view-link">{isOpen ? "Close profile" : "View profile →"}</span>
                                                    </div>
                                                </Link>
                                            </li>
                                        );
                                    })}
                                </ul>
                            )}
                        </>
                    )}
                </div>

                <aside className="browse-side">
                    {openId ? (
                        <Outlet />
                    ) : (
                        <div className="card state-card detail-empty">
                            <div className="state-icon">👈</div>
                            <h2>Select a profile</h2>
                            <p>Pick a listing on the left to see its skills, services and what it is looking for.</p>
                        </div>
                    )}
                </aside>
            </div>
        </section>
    );
}

function SkeletonList() {
    return (
        <ul className="profile-list" aria-busy="true" aria-label="Loading profiles">
            {Array.from({length: 4}, (_, i) => (
                <li key={i} className="card skeleton-card">
                    <div className="skeleton" style={{width: "60%", height: 22}} />
                    <div className="skeleton" style={{width: "40%", height: 14}} />
                    <div className="skeleton" style={{width: "100%", height: 40}} />
                </li>
            ))}
        </ul>
    );
}
