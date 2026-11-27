import {useRef, type ReactNode} from "react";
import {Link, useLocation, useParams} from "react-router";
import {formatDate, initials, useProfile, useScrollIntoViewOnMobile} from "../hooks/profiles";
import {Meta, PillList, TypePill} from "../components/ui";

// Detail panel shown in the right column of the browse view.
// Kept compact so the whole profile fits on screen without scrolling.
export default function ProfilePage() {
    const {id = ""} = useParams();
    const {search} = useLocation();
    const {profile, error} = useProfile(id);
    const ref = useRef<HTMLDivElement>(null);
    useScrollIntoViewOnMobile(ref, id);

    if (error) {
        return (
            <div ref={ref} className="card state-card error" role="alert">
                <div className="state-icon">⚠️</div>
                <h2>{error}</h2>
                <Link to={{pathname: "/", search}} className="btn btn-outline">
                    Close
                </Link>
            </div>
        );
    }

    if (!profile) {
        return (
            <div ref={ref} className="card skeleton-card" aria-busy="true">
                <div className="skeleton" style={{width: 40, height: 40, borderRadius: 6}} />
                <div className="skeleton" style={{width: "60%", height: 24}} />
                <div className="skeleton" style={{width: "40%", height: 14}} />
                <div className="skeleton" style={{width: "100%", height: 60}} />
            </div>
        );
    }

    return (
        <div ref={ref} className="card detail">
            <header className="detail-head">
                <div className="avatar" aria-hidden="true">
                    {initials(profile.name)}
                </div>
                <div className="detail-title">
                    <div className="detail-name-row">
                        <h1>{profile.name}</h1>
                        <TypePill type={profile.type} />
                    </div>
                    <Meta sector={profile.sector} region={profile.region} />
                </div>
                <div className="detail-actions">
                    {profile.website && (
                        <a href={profile.website} target="_blank" rel="noreferrer" className="btn btn-sm">
                            Website ↗
                        </a>
                    )}
                    <Link to={{pathname: "/", search}} className="detail-close" aria-label="Close profile">
                        ✕
                    </Link>
                </div>
            </header>

            <p className="detail-description">{profile.description}</p>

            <dl className="detail-sections">
                <Row title="Skills">
                    {profile.skills.length > 0 ? <PillList items={profile.skills} /> : <Empty />}
                </Row>
                <Row title="Services">
                    <TextList items={profile.services} />
                </Row>
                <Row title="Looking for">
                    <TextList items={profile.needs} />
                </Row>
            </dl>

            <footer className="detail-footer">
                <span>
                    Languages: <TextList items={profile.languages.map((l) => l.toUpperCase())} />
                </span>
                <span>
                    Found on:{" "}
                    {profile.sources.map((s, i) => (
                        <span key={s.original_url}>
                            {i > 0 && ", "}
                            <a href={s.original_url} target="_blank" rel="noreferrer" className="text-link">
                                {s.name}
                            </a>
                        </span>
                    ))}
                </span>
                <span>Updated {formatDate(profile.updated_at)}</span>
            </footer>
        </div>
    );
}

function Row({title, children}: {title: string; children: ReactNode}) {
    return (
        <div className="detail-row">
            <dt>{title}</dt>
            <dd>{children}</dd>
        </div>
    );
}

function TextList({items}: {items: string[]}) {
    return items.length > 0 ? <>{items.join(", ")}</> : <Empty />;
}

function Empty() {
    return <span className="empty-note">Nothing listed</span>;
}
