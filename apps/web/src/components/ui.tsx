import {TYPE_LABELS, type ProfileType} from "../api";

// Small building blocks shared by the pages.

export function TypePill({type}: {type: ProfileType}) {
    return (
        <span className="type-pill" data-type={type}>
            {TYPE_LABELS[type]}
        </span>
    );
}

export function PillList({items, accent = false, max}: {items: string[]; accent?: boolean; max?: number}) {
    const shown = max === undefined ? items : items.slice(0, max);
    const hidden = items.length - shown.length;
    return (
        <ul className="pill-list">
            {shown.map((item) => (
                <li key={item} className={accent ? "pill pill-accent" : "pill"}>
                    {item}
                </li>
            ))}
            {hidden > 0 && <li className="pill">+{hidden}</li>}
        </ul>
    );
}

export function Meta({sector, region}: {sector: string | null; region: string | null}) {
    return (
        <div className="meta-row">
            <span>
                <Icon path="M3 7h18v13H3zM8 7V4h8v3" /> {sector ?? "No sector"}
            </span>
            <span>
                <Icon path="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21zM12 12a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z" />{" "}
                {region ?? "No region"}
            </span>
        </div>
    );
}

export function Icon({path, size = 14}: {path: string; size?: number}) {
    return (
        <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d={path} />
        </svg>
    );
}
