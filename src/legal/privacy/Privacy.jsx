import { ArrowLeft, ArrowUpRight, Check } from 'lucide-react';

const UPDATED = 'October 24, 2026';

const SECTIONS = [
  {
    id: 'controller',
    title: 'Controller and anonymity model',
    lead: 'Who is responsible for your data, and why we publish so little about them.',
    body: [
      'Controller: Kinora (the “Controller” or “Operator”). The site is operated under the Kinora brand by a natural person who has deliberately chosen anonymity: their name, identification number, telephone number and physical address are not published. For all purposes of this Policy and Colombian Law 1581 of 2012, the Controller is sufficiently identified by brand (Kinora), main domain (https://kinora.com.co), contact email (contact@kinora.com.co) and country of operation (Colombia).',
      'The omission of the name and identification number does not affect the validity of consent, the ownership of rights and obligations, or the exercise of data-subject rights, which are handled through the official email. Kinora may disclose its identity, in whole or in part, where required by a competent judicial or administrative authority (including the Superintendence of Industry and Commerce), where necessary to defend its rights in a dispute, where required by an applicable rule, or where convenient to prove an authorisation or handle a claim.',
      'Identifiers that Kinora does not control: domain registration may expose holder data depending on the registrar’s privacy policy (for example, WHOIS data). Kinora does not control that information and does not consider it part of this Policy. If the Operator later incorporates a company, obtains a tax ID, enables payments or appoints a representative, this section will be updated accordingly without affecting prior processing.',
      'The Operator handles requests, queries and claims through contact@kinora.com.co with the subject “Kinora – Privacy”. There is no telephone or in-person support, by decision of anonymity and data minimisation.'
    ]
  },
  {
    id: 'scope',
    title: 'Scope and territorial reach',
    body: [
      'This Policy applies to visitors of the site; users who interact with the search engine, detail pages, players, subtitles, lists or preferences; and data processed through cookies, local storage, server logs and integrated third-party services (advertising, analytics, metadata, subtitles, players, images).',
      'It does not govern third-party sites, players or services linked or embedded on the site, which are subject to their own policies (section 9). The site is available in several languages and is aimed primarily at users in Colombia and Latin America, without excluding users in other regions. Section 11 sets out rights applicable in other jurisdictions.'
    ]
  },
  {
    id: 'definitions',
    title: 'Definitions',
    body: [
      'Anonymisation: a process that prevents associating data with an identified or identifiable person. Authorisation: prior, express and informed consent of the data subject. Cookie notice: a first-layer mechanism that informs and records the choice on non-essential cookies. CMP: a consent management platform that records and communicates user choices to third parties that require them. Cookie: a text file stored by the browser and returned to the server that issued it. Personal data: information linked or associable to an identified or identifiable natural person (an IP address or device identifier may qualify). Processor: a party processing data on behalf of the Controller. GPC (Global Privacy Control): a browser privacy preference signal communicating an objection to the sale or sharing of data. Pixel / web beacon: a minimal invisible resource that records a visit. Pseudonymisation: processing that prevents attributing data to a person without additional information. Controller: the party deciding on the database and processing (Kinora, section 1). Data subject: the natural person whose data is processed. Processing: any operation on personal data. Transfer / transmission: sending to another Controller / communicating to a Processor.'
    ]
  },
  {
    id: 'principles',
    title: 'Principles',
    body: [
      'Kinora guides processing, as reasonably applicable, by legality and informed legitimate purpose; freedom and consent where required by law; transparency; truthfulness and quality in what depends on the Controller; security and confidentiality; restricted access and circulation; and minimisation, meaning only what is necessary is processed. Kinora also applies its own guiding principle: the less identifiable data, the better, which explains the Operator’s anonymity and the preference for storing data on the user’s device.'
    ]
  },
  {
    id: 'data',
    title: 'Data we may process',
    body: [],
    groups: [
      {
        title: 'Technical and browsing data',
        items: [
          'IP address and approximate location derived from it (approximate country or city).',
          'Browser, operating system, device type, language and resolution.',
          'Pages and routes visited, date and time, referring URL.',
          'Session or device identifiers.',
          'Server logs and error codes.'
        ]
      },
      {
        title: 'Interaction data',
        items: [
          'Search queries.',
          'Titles or catalogue identifiers viewed or played.',
          'Language, audio or subtitle preferences, and filters used.',
          'Technical player events (start, error, quality change), in aggregate or technical form.',
          'Choice of playback provider, when the user makes one.'
        ]
      },
      {
        title: 'Data stored on your device',
        items: [
          'Lists, favourites and preferences saved in browser local storage. They are not sent to our servers unless a future feature expressly says so.',
          'Subtitle or reusable resource cache.',
          'Local record of your cookie choice (categories accepted, date and version of the notice).'
        ]
      },
      {
        title: 'Communication data',
        items: [
          'Name or pseudonym, email and message content when you write to the official address.',
          'Data provided in copyright notices, privacy requests or claims.'
        ]
      },
      {
        title: 'Advertising and third-party data',
        items: [
          'Advertising identifiers, cookies and usage data processed by ad networks and their partners under their own policies (section 9 and Annex II).'
        ]
      }
    ],
    body2: [
      'Data we do not request: Kinora does not deliberately request sensitive data (health, biometrics, beliefs, sexual life, ethnic origin, among others). You are not obliged to provide it. Titles you consult may reflect your interests, but are not used to infer sensitive categories beyond an indicative level.',
      'Data we do not process (for now): there are no accounts, passwords, profiles or authentication; no centralised viewing history on a server; and no payment data until paid features exist.'
    ]
  },
  {
    id: 'purposes',
    title: 'Purposes of processing',
    body: [
      'Data is processed to: (a) provide, maintain and improve the service and its features; (b) enable search, browsing, playback and subtitles, and remember preferences; (c) ensure security and prevent fraud, abuse, aggressive scraping, attacks and misuse; (d) produce aggregate statistics and technical diagnostics; (e) respond to requests, queries, claims and legal requirements, including copyright notices; (f) display advertising, personalised only where appropriate and with your authorisation; (g) comply with legal obligations and defend rights in disputes; and (h) personalise basic interface aspects (language, last interaction).',
      'Your data will not be used for different purposes without informing you and, where required by law, without new authorisation.'
    ]
  },
  {
    id: 'bases',
    title: 'Legal bases, authorisation and withdrawal',
    body: [
      'Colombia: processing requires prior, express and informed authorisation, except for legal exceptions. It may be given in writing, orally or through unequivocal conclusive conduct (for example, accepting or configuring the cookie notice, or writing to the email address). Silence is not presumed to be authorisation.',
      'Essential technical data: processing strictly necessary to deliver the site and keep it secure relies on the user’s access request, Kinora’s legitimate interest in security and abuse prevention, and compliance with legal obligations.',
      'Non-essential cookies and personalised advertising: only with prior authorisation collected in the cookie notice. You may accept, reject or configure, and change your choice at any time (section 8.6). Kinora keeps evidence of authorisations: local record of the cookie choice (categories, date, version) and, where applicable, the email sent.',
      'You may withdraw authorisation and request deletion, subject to any legal or contractual retention duty (sections 10 and 13).'
    ]
  },
  {
    id: 'cookies',
    title: 'Cookies, local storage and similar technologies',
    body: [
      'The site uses first- and third-party cookies, local storage (localStorage / sessionStorage), pixels and equivalent technologies. This section also applies to those technologies even if they are not cookies in the strict sense.',
      'General consent rule: non-essential technologies are not activated before your consent where required by law. There are no pre-ticked boxes or cookie walls. Refusal must be as easy and visible as acceptance.',
      'Categories: (a) strictly necessary — basic operation, security, load balancing and remembering your choice; no consent required. Provider: Kinora and its network/security provider. Duration: that of each identifier (Annex I). (b) Preferences and functionality — language, filters, lists, subtitle cache; considered necessary for a function you request, declared transparently. Provider: Kinora (browser local storage). (c) Analytics and measurement — aggregate usage statistics, where possible without persistent identifiers; consent required where the law demands it. (d) Advertising — targeting, measurement and frequency capping, served by third-party networks (for example, Google AdSense and its partners); consent required for personalisation and non-essential cookies. (e) Third-party content — catalogue images, trailers and, where used, embedded players or subtitles; they may set their own cookies when your browser connects directly to them.',
      'How resources load matters. When a resource is served through our proxy (for example, video streams resolved and proxied by our backend or Worker), the originating third party usually sees our server’s IP rather than yours, and that third party’s cookies are usually handled server-side, so cookies are not always deposited in your browser; the proxy may also send a normalised browser identifier instead of your real one. When a resource is loaded directly by your browser (for example, catalogue images, YouTube trailers or ads), your browser connects to the third party, which receives your IP, the referrer and technical data, and may set its own cookies.',
      'Consent notice and management: on the first visit a first-layer cookie notice is shown with Accept all, Reject all and Configure actions, with granular control by category. The choice is recorded (categories, date and time, notice version, local identifier) so it can be evidenced. The choice is renewed when the inventory changes materially and, as good practice, at least every 12 months. You may reopen the panel at any time through the permanent “Cookie settings” link in the footer, or clear cookies and site data from your browser.',
      'Consequences of refusing: the site keeps working. Without consent, analytics and personalised advertising are not activated (non-personalised advertising may be shown); lists and preferences keep working because they live on your device; and some content third parties may still set cookies if their content is loaded directly. Kinora aims to respect the Global Privacy Control signal as an objection to sale or sharing where the law recognises it, and as a rejection of non-essential cookies to the extent the implementation allows. “Do Not Track” is not uniform across browsers and its interpretation is not guaranteed.',
      'Google advertising and Consent Mode: where Google advertising is served, Kinora may implement Google Consent Mode (ad storage, user data, personalisation and analytics signals) so tags behave according to your choice. For users in the EEA, UK and Switzerland, Google requires a certified consent platform integrated with the advertising industry framework; if unavailable, Google may limit personalised advertising (sections 9.3 and 11.1). You can block or delete cookies and clear site data, manage personalised advertising preferences at https://adssettings.google.com, and use self-regulatory portals such as https://www.aboutads.info/choices and https://www.youronlinechoices.eu. The concrete inventory of cookies and storage keys, provider, purpose, duration and consent requirement is kept updated in Annex I.'
    ]
  },
  {
    id: 'third-parties',
    title: 'Third parties, processors, transfers and the proxy effect',
    body: [
      'Categories of third parties involved: hosting and cloud servers; distribution network, proxy and security; metadata and catalogue images; subtitles; source video players or streams; advertising and its partners; and, where applicable, analytics and email.',
      'Direct connections from your browser: to display posters, trailers, ads or certain players, your browser may connect directly to third parties, which receive your IP, browser type, referrer and other technical data and may set their own cookies. Kinora does not control that processing. Google and other third parties may place and read cookies, use web beacons or your IP to collect information derived from the advertising shown. How Google uses partner data: https://www.google.com/policies/privacy/partners/',
      'Roles: some providers act as Processors (processing data on behalf of Kinora under a contract or equivalent conditions: for example, hosting and proxy). Others act as independent Controllers of their own processing (for example, Google, the metadata provider and video providers) when they collect data directly from your browser or for their own purposes.',
      'Proxy effect (privacy advantage): when a resource is served by our proxy, the originating third party does not directly receive your IP or real browser identifier, but those of Kinora’s infrastructure. This reduces the footprint and cross-site correlation, and is a deliberate feature of the service design.',
      'International transfers and transmissions: servers and providers may be outside Colombia (for example, the United States or the European Union). International transfers are made to countries with a recognised adequate level or based on applicable legal exceptions, including your express and unequivocal authorisation where appropriate, collected in the cookie notice. Transmissions to Processors are governed by conditions requiring security and confidentiality.',
      'Main providers: reference list in Annex II, kept updated. It may change without prior notice for technical reasons; relevant changes are reflected in the Annex. Third-party policies: we recommend reviewing the policies of Google, the metadata provider and subtitle and video providers. External links are not governed by this Policy.',
      'No sale of databases: Kinora does not commercially transfer contact databases. However, third-party advertising may constitute a “sale” or “sharing” within the meaning of some US state laws (section 11.2).'
    ]
  },
  {
    id: 'rights',
    title: 'Your rights (Colombia)',
    body: [
      'Under Law 1581 of 2012 you may: (a) know, update and rectify your data; (b) request proof of the authorisation granted; (c) be informed, upon request, of the use made of your data; (d) file complaints with the SIC for infringements, after exhausting the consultation or claim procedure with Kinora; (e) withdraw authorisation and/or request deletion, subject to any legal or contractual retention duty; and (f) access your data free of charge at least once every calendar month and whenever there are substantial changes to this Policy.',
      'Who may exercise them: the data subject proving identity, their successors, representative or attorney, or anyone acting under a stipulation in favour of another. Rights of children and adolescents are exercised by those authorised to represent them.',
      'How to exercise them: write to contact@kinora.com.co (subject “Kinora – Privacy”) stating your name or pseudonym and contact method; a description of the facts or request; information allowing identity verification where necessary; and data helping locate the processing (approximate date, page visited, IP if known). Exercising these rights is free of charge. As there are no accounts, Kinora locates data by technical references (date, IP, email). Some processing may not be unequivocally attributable to you; in that case we will tell you clearly and with reasons.',
      'Time limits: consultations — maximum ten (10) business days from receipt; if not possible, the reasons and service date will be communicated, not exceeding five (5) additional business days. Claims (correction, update, deletion, withdrawal or alleged non-compliance) — if incomplete, you will be asked to complete it within five (5) days; after two (2) months without response, withdrawal is deemed. Once complete, the claim is handled within a maximum of fifteen (15) business days from the day after receipt; if not possible, reasons and a new date will be communicated, not exceeding eight (8) additional business days. While it is being processed, “claim in progress” will be noted. Authority: if you do not obtain a satisfactory response, you may contact the Superintendence of Industry and Commerce, Delegation for Personal Data Protection: https://www.sic.gov.co'
    ]
  },
  {
    id: 'other',
    title: 'Users in other jurisdictions',
    body: [
      'EEA, United Kingdom and Switzerland (GDPR / UK GDPR / FADP): Controller: Kinora, as per section 1. Legal bases: consent (non-essential cookies, personalised advertising); legitimate interest (security, abuse prevention, service improvement); handling data-subject requests; compliance with legal obligations. Rights: access, rectification, erasure, restriction, portability, objection — including objection to processing based on legitimate interest — not to be subject to automated decisions with significant effects, and withdrawal of consent at any time without affecting prior lawfulness. Complaint: you may contact your national supervisory authority (for example, the AEPD in Spain). Transfers outside your country: recognised safeguards apply (adequacy decisions or standard contractual clauses). Cookies: in addition to the GDPR, e-privacy rules apply; non-essential cookies are activated only after prior consent. EU representative: because the Controller is established outside the Union and offers the service to EU users, an EU representative may be appointed; until formally appointed, requests are handled through the official email, which acts as contact point. Age: the service is intended for over-18s; if a minor uses it under a representative’s responsibility, section 12 applies.',
      'United States (California and states with privacy laws): no personal information is sold for money. Third-party advertising may constitute a “sale” or “sharing” for cross-context behavioural advertising under some state laws. You may opt out through “Cookie settings”, through preference signals such as GPC where your browser sends it and the law recognises it, or by writing to the official email. Depending on your state, you may request to know, access, correct or delete, obtain information about categories and recipients, and limit the use of sensitive personal information. There will be no discrimination for exercising these rights. No enhanced identity verification applies because there are no accounts; the available technical reference is used.',
      'Latin America: although the main basis is Colombian law, Kinora will handle equivalent requests from users in other countries to the applicable extent: Mexico (LFPDPPP), Brazil (LGPD), Argentina (Law 25.326), Chile (Law 19.628 and its reform), Peru (Law 29733), Ecuador (Organic Data Protection Law), Uruguay (Law 18.331), Paraguay (Law 6534) and other concordant rules (Annex III). Other countries: users in other jurisdictions will have the equivalent rights recognised by their local law, handled to the extent applicable.'
    ]
  },
  {
    id: 'minors',
    title: 'Minors',
    body: [
      'The service is intended for persons over eighteen (18) years of age and does not intentionally collect data from children and adolescents. In Colombia, processing data of minors is prohibited except for data of a public nature and cases meeting legal requirements (best interests, respect for fundamental rights and authorisation from the representative). Personalised advertising is not directed at users known to be under 13. If a legal representative considers that a minor provided data, or if Kinora detects that it received such data, it may review or delete it upon request.'
    ]
  },
  {
    id: 'retention',
    title: 'Retention and validity',
    body: [
      'Data is retained only for the reasonable time necessary for the purposes and to comply with legal or contractual obligations, after which it is deleted or anonymised. Reference periods: technical server logs — up to 90 days, with the possibility of truncating or anonymising the IP; emails and requests (queries, claims, privacy) — duration of handling plus 2 additional years; copyright notices and their processing — 5 years, for the defence of rights; data on your device (local storage, cache) — until you delete it or the application purges it for space; cookies and data held by third parties — according to each provider.',
      'Databases remain valid while the purposes in section 6 subsist. This Policy is in force from its effective date. Kinora is not obliged to retain data that is not necessary and may purge it early.'
    ]
  },
  {
    id: 'security',
    title: 'Security and incident notification',
    body: [
      'Kinora applies reasonable technical, human and administrative measures: HTTPS encryption for communications with the site, security headers, access control to infrastructure, server-side data minimisation, restriction of unnecessary logs, rate limits and a proxy to avoid exposing user identifiers. No system is invulnerable; users should keep their browser and device up to date.',
      'If security breaches put data subjects’ information at risk, Kinora will inform the SIC in accordance with the law and, where appropriate, affected individuals, indicating the nature of the incident, the data compromised, the measures taken and recommendations.',
      'User role: do not reuse passwords (even though there are no accounts), be wary of player pop-ups, and verify the URL before installing anything a third party suggests.'
    ]
  },
  {
    id: 'profiling',
    title: 'Advertising, profiling and automated decisions',
    body: [
      'Advertising may be based on interests inferred by third-party advertisers from your browsing, according to the cookies you authorise. As a general rule, Kinora does not make automated decisions producing significant legal effects, beyond the technical operation of the service and basic personalisation of the interface or third-party-managed ads. Non-personalised advertising may be displayed without non-essential cookies, depending on provider settings.'
    ]
  },
  {
    id: 'changes',
    title: 'Changes to this Policy',
    body: [
      'Kinora may update this Policy for legal, technical or service changes. The current version will be published with its date and version number. Material changes relating to the identification of the Controller or the purposes will be communicated with a visible notice on the site before implementation or, at the latest, when implemented. If purposes change, new authorisation will be requested. For other changes, continued use implies awareness of the new version, without prejudice to specific consents required. The version history is published in Annex IV.'
    ]
  },
  {
    id: 'contact',
    title: 'Contact',
    body: [
      'Email: contact@kinora.com.co — suggested subject: “Kinora – Privacy”. Website: https://kinora.com.co. Controller details: section 1.'
    ]
  },
  {
    id: 'transparency',
    title: 'Additional transparency',
    body: [
      'Kinora does not sell contact data lists collected on the site. Third-party advertising may involve processing of technical identifiers by those third parties to display and measure ads. Users may limit tracking with browser controls, ad blockers or operating-system settings, accepting possible functionality limitations; ad blockers are compatible with the service. Kinora aims for the experience to work even without non-essential cookies: the core of the service does not depend on tracking.'
    ]
  }
];

const COOKIES = [
  ['Necessary', 'kinora:consent (localStorage)', 'Kinora', 'Record your cookie choice (categories, date, version)', 'Until deleted', 'No'],
  ['Necessary', 'Edge security / bot cookie', 'Network / security provider', 'Mitigate bots and abuse', 'Short (minutes)', 'No'],
  ['Preference', 'kinora:mi-lista (localStorage)', 'Kinora', 'Save your titles', 'Until deleted', 'No'],
  ['Preference', 'kinora:prefs (localStorage)', 'Kinora', 'Language, audio, filters', 'Until deleted', 'No'],
  ['Preference', 'kinora:subs-cache (localStorage / IndexedDB)', 'Kinora', 'Reuse downloaded subtitles', 'Until deleted or purged', 'No'],
  ['Analytics', 'Provider-specific (e.g. _ga, _ga_*)', 'Analytics provider', 'Measure usage in aggregate', '13–24 months', 'Yes'],
  ['Advertising', 'Provider-specific (e.g. __gads, __gpi, IDE)', 'Ad network and partners', 'Targeting, measurement, frequency', 'Up to 13 months', 'Yes'],
  ['Third-party content', 'Provider-specific (e.g. VISITOR_INFO1_LIVE, YSC on YouTube)', 'Content provider', 'Play trailers / embeds and measure', 'Session to 12 months', 'Depends on load']
];

const THIRD_PARTIES = [
  ['Hosting and server provider', 'Processor', 'Run the backend and serve the site', 'Outside Colombia (e.g. US)'],
  ['Distribution, proxy and security network', 'Processor', 'Media proxy, cache, abuse mitigation', 'Global network'],
  ['Metadata and image provider', 'Independent controller', 'Synopsis, posters, ratings, IDs', 'Per provider'],
  ['Source video providers', 'Independent controller', 'Playback streams', 'Variable (may change)'],
  ['Subtitle providers (if applicable)', 'Independent controller', 'Subtitles', 'Variable'],
  ['Ad network and partners', 'Independent controller', 'Ads and measurement', 'Global'],
  ['Trailer video platform (if applicable)', 'Independent controller', 'Trailers', 'Global'],
  ['Analytics (if applicable)', 'Processor or controller', 'Statistics', 'Global'],
  ['Email provider', 'Processor', 'Receive and answer messages', 'Global']
];

const JURISDICTIONS = [
  ['Colombia', 'Law 1581 of 2012 and regulatory decrees', 'Know, update, rectify, prove authorisation, be informed of use, complain to the SIC, withdraw, delete, access'],
  ['EEA / UK / Switzerland', 'GDPR, UK GDPR, FADP', 'Access, rectification, erasure, restriction, portability, objection, withdrawal of consent'],
  ['California and other US states', 'State privacy laws', 'Know, access, correct, delete, opt out of sale/sharing, non-discrimination'],
  ['Mexico', 'LFPDPPP', 'Access, rectification, cancellation, objection, withdrawal'],
  ['Brazil', 'LGPD', 'Confirmation, access, correction, anonymisation, portability, deletion, information'],
  ['Argentina, Chile, Peru, Ecuador, Uruguay, Paraguay', 'Local data protection laws', 'Access, rectification, erasure, objection and other equivalent rights']
];

const VERSIONS = [
  ['1.0', '10/23/2026', 'Initial version'],
  ['1.1', '10/23/2026', 'Structural and cookie adjustments'],
  ['2.0', '10/24/2026', 'Operator anonymity model; rewritten cookies section (inventory, granular consent, withdrawal, privacy signals, Consent Mode); proxy effect; incident, retention, LatAm jurisdiction and EU representative sections; Annexes I–IV']
];
const AnnexTable = ({ title, head, rows }) => (
  <section className="terms__section privacy__annex">
    <h2>{title}</h2>
    <div className="privacy__table-wrap">
      <table>
        <thead>
          <tr>
            {head.map(cell => (
              <th key={cell}>{cell}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr key={index}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </section>
);

export default function Privacy() {
  return (
    <div className="terms">
      <header className="terms__bar">
        <a className="terms__brand" href="/">
          <img src="/assets/kinora-logo.svg" alt="" width={22} height={22} />
          Kinora
        </a>
        <a className="terms__back" href="/">
          <ArrowLeft size={15} />
          Back to Kinora
        </a>
      </header>

      <div className="terms__hero">
        <div className="terms__hero-inner">
          <span className="terms__kicker">Privacy</span>
          <h1>Your data, kept to the minimum.</h1>
          <p>
            What we process, why, and what we deliberately avoid. No accounts, no contact lists for sale, and as little
            as possible on our servers.
          </p>
          <div className="terms__meta">
            <span>Version 2.0</span>
            <span>Last updated: {UPDATED}</span>
            <span>kinora.com.co</span>
          </div>
        </div>
      </div>

      <div className="terms__layout">
        <aside className="terms__index" aria-label="Contents">
          <p>Contents</p>
          <nav>
            {SECTIONS.map(section => (
              <a key={section.id} href={`#${section.id}`}>
                {section.title}
              </a>
            ))}
            <a href="#annexes">Annexes</a>
          </nav>
        </aside>

        <article className="terms__content">
          {SECTIONS.map(section => (
            <section key={section.id} id={section.id} className="terms__section">
              <h2>{section.title}</h2>
              {section.lead ? <p className="terms__lead">{section.lead}</p> : null}
              {section.body.map((paragraph, index) => (
                <p key={index}>{paragraph}</p>
              ))}
              {section.groups
                ? section.groups.map(group => (
                    <div key={group.title} className="privacy__group">
                      <h3>{group.title}</h3>
                      <ul>
                        {group.items.map(item => (
                          <li key={item}>
                            <Check size={12} />
                            <span>{item}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))
                : null}
              {section.body2 ? section.body2.map((paragraph, index) => <p key={`b${index}`}>{paragraph}</p>) : null}
            </section>
          ))}

          <div className="terms__section" id="annexes">
            <h2>Annexes</h2>
            <p className="terms__lead">The detail behind the policy.</p>
            <p>
              Inventory of cookies and storage keys, the third parties involved, the rights recognised in each
              jurisdiction and the version history of this Policy.
            </p>
          </div>

          <AnnexTable
            title="Annex I — Cookie and storage inventory"
            head={['Category', 'Name / key', 'Provider', 'Purpose', 'Duration', 'Consent?']}
            rows={COOKIES}
          />

          <AnnexTable
            title="Annex II — Third parties, role and location"
            head={['Third party / category', 'Role', 'Purpose', 'Typical location']}
            rows={THIRD_PARTIES}
          />

          <AnnexTable
            title="Annex III — Rights by jurisdiction"
            head={['Jurisdiction', 'Reference law', 'Key rights']}
            rows={JURISDICTIONS}
          />

          <AnnexTable title="Annex IV — Version history" head={['Version', 'Date', 'Changes']} rows={VERSIONS} />

          <p className="privacy__note">
            When content is served through Kinora’s proxy, origin cookies may be handled server-side and not deposited
            in your browser.
          </p>

          <div className="terms__end">
            <p>Questions about this Policy?</p>
            <a href="mailto:contact@kinora.com.co">
              contact@kinora.com.co
              <ArrowUpRight size={14} />
            </a>
          </div>
        </article>
      </div>

      <footer className="terms__foot">
        <span>© 2026 Kinora</span>
        <span>
          <a href="/terms.html">Terms of Service</a>
          <a href="/">Home</a>
        </span>
      </footer>
    </div>
  );
}
