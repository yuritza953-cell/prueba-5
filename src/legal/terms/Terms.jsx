import { ArrowLeft, ArrowUpRight } from 'lucide-react';

const UPDATED = 'October 24, 2026';

const SECTIONS = [
  {
    id: 'short',
    title: 'In short',
    body: [
      'Kinora is a search engine, index and interface for finding movies, series and anime. Catalogue information comes from third parties, mainly a metadata provider.',
      'Kinora does not host or store video or audio files on its servers. When playback is available, it is provided by third parties.',
      'Kinora does not own the rights to the works and does not guarantee that third-party sources are lawful in every country, available, or safe. You are responsible for using the service in compliance with the law of your country.',
      'The operator runs the service under the Kinora brand and does not publish its name or identification number.',
      'If you are a rights holder and material accessible from the site affects you, you may request removal under section 6.',
      'The site displays advertising and uses cookies. See section 8 and the Privacy Policy.',
      'You must be at least 18 years old.'
    ]
  },
  {
    id: 'operator',
    title: '1. Operator, anonymity and nature of the service',
    body: [
      '1.1. Operator. The site is operated under the Kinora brand by a natural person domiciled in Colombia who has chosen not to publish their name or identification number (the “Operator” or “Kinora”). Contact: contact@kinora.com.co. Identification by brand, domain and email is sufficient for all purposes of these Terms, without prejudice to disclosing identity when required by an authority, a legal process, or the defence of its rights (Privacy Policy, section 1).',
      '1.2. Nature. Kinora is an informational and entertainment platform that lets users consult metadata for audiovisual works obtained from third parties and offers an interface through which users may access reproductions provided by third parties when technical sources are available.',
      '1.3. Kinora is not a streaming service. It does not host, store or distribute video or audio files from its own servers. It is not a producer, distributor, licensee or holder of copyright or related rights over the works, and does not present itself as such. The presence of a work in the catalogue does not imply that Kinora holds licences for it.',
      '1.4. Instrumental activity. Kinora’s activity is predominantly instrumental: it indexes, links, embeds and, where appropriate, acts as a technical intermediary (for example, by relaying or proxying streams for compatibility and privacy). Kinora relies on the linking nature of its activity and on its lack of editorial control over content hosted by third parties.',
      '1.5. Catalogue. Catalogue information (synopsis, posters, ratings, cast and related data) comes from external providers. Kinora does not guarantee its accuracy, currency or completeness. Ratings are usually aggregates of third-party user votes, not official reviews.',
      '1.6. Independence. Kinora is not affiliated with, sponsored by, or certified by metadata, video, advertising or trailer platform providers, unless expressly stated.'
    ]
  },
  {
    id: 'acceptance',
    title: '2. Acceptance, age and capacity',
    body: [
      '2.1. Accessing, browsing or using the service implies acceptance of these Terms. Acceptance is independent of data and cookie authorisations, which are governed by the Privacy Policy and the cookie notice. If you do not agree, you must refrain from using the service.',
      '2.2. The service is intended for persons over eighteen (18) years of age. If a legal representative allows a minor to use it, it is their responsibility to supervise that use, to consider that some works contain themes, language or images unsuitable for minors, and to ensure compliance with these Terms.',
      '2.3. Anyone acting on behalf of a legal entity declares that they have sufficient authority to bind it.'
    ]
  },
  {
    id: 'service',
    title: '3. Description of the service and scope',
    body: [
      '3.1. The service may include, without limitation: (a) search and consultation of titles and metadata; (b) detail pages and associated information; (c) access to third-party reproductions where sources exist; (d) subtitle management through external providers; (e) list, favourites and preference features stored in the browser’s local storage; and (f) third-party advertising spaces.',
      '3.2. No accounts. The site can be used without registration. If accounts are enabled in the future, the conditions will be published and the data collected will be disclosed before use.',
      '3.3. Lists on your device. Lists and preferences are stored locally. The user accepts the consequences: there is no server backup, no synchronisation between devices, and the list is lost if site data is cleared or the browser or device changes. Kinora is not responsible for that loss.',
      '3.4. Changes to the service. Kinora may modify, suspend, limit or discontinue the service, any feature, provider, catalogue or interface, temporarily or permanently, with or without prior notice, for technical, legal, security, operational or any other legitimate reason. In particular, playback sources may be added, rotated or removed without creating a right to any specific result.',
      '3.5. Free access. Access is free, without prejudice to advertising and connectivity costs borne by the user. If paid features are introduced, their conditions (price, payment methods, term, cancellation and applicable consumer rights) will be published in advance.',
      '3.6. Compatibility. The service is designed for modern browsers. Playback may depend on browser and third-party technologies and may not work on old devices, with aggressive extensions, with interfering blockers, or on limited connections.',
      '3.7. API and programmatic use. Internal routes may be queried programmatically on a reasonable basis, always with attribution and without abuse, unless stated otherwise.'
    ]
  },
  {
    id: 'use',
    title: '4. Permitted use and prohibitions',
    body: [
      '4.1. The user agrees to use the site in accordance with the law, public order and these Terms.',
      '4.2. The following are expressly prohibited: (a) using the service for unlawful purposes or to infringe intellectual property, industrial, image, honour or privacy rights of third parties; (b) circumventing technical protection measures, access controls, signatures, tokens, rate limits or security systems; (c) reverse engineering, unauthorised mass scraping, abusive automated data mining or deliberate overloading of the infrastructure; (d) introducing malware, malicious scripts or code that damages or interferes with the site or third-party equipment; (e) impersonating identities, falsifying network metadata or manipulating headers for fraudulent purposes; (f) commercialising, reselling or exploiting the service or its contents without authorisation; (g) using the site in a way that creates civil, criminal or administrative liability for Kinora or third parties; (h) systematically extracting, republishing or reusing databases, subtitles, metadata or interfaces beyond personal and legitimate use; (i) downloading, recording, copying, redistributing or publicly communicating accessible works, unless permitted by law or the rights holder; (j) presenting the site as your own or suggesting a non-existent affiliation; (k) framing the site so as to hide or misrepresent its origin, unless authorised; (l) removing, hiding or altering proprietary notices or attributions.',
      '4.3. Non-compliance may result in immediate suspension of access, blocking of IP addresses or devices, and the relevant legal actions.'
    ]
  },
  {
    id: 'third-party',
    title: '5. Third-party content, playback and sources',
    body: [
      '5.1. The site may display, embed, link to or proxy content, players, files, subtitles, advertisements or third-party services (“Third-Party Content”).',
      '5.2. Kinora does not control Third-Party Content or those who host it, and does not guarantee its legality, availability, quality, synchronisation, language, security or permanence. It may become unavailable, change origin or show errors without obliging Kinora to guarantee a specific result.',
      '5.3. The existence of a detail page does not imply the existence of an operational or lawful source at all times or in every country.',
      '5.4. Third parties may apply their own terms and policies, use cookies, display advertisements, open pop-ups or redirect, and receive technical data from your device. Users should act with caution and should not install software or download files offered through pop-ups or redirects, and may rely on browser security tools.',
      '5.5. Proxy and privacy. When playback is served through Kinora’s infrastructure, the originating third party may not directly see your IP address or real browser identifier. This is a design feature, not an absolute guarantee, as it depends on the provider and load mode.',
      '5.6. Geoblocking. Some sources are restricted by country or region. Availability may vary according to approximate geolocation derived from the IP address.',
      '5.7. User responsibility. The user is solely responsible for verifying that their access and use comply with the law applicable in their jurisdiction, including copyright, public communication, private copying and territorial restrictions.'
    ]
  },
  {
    id: 'copyright',
    title: '6. Copyright: notice and takedown',
    body: [
      '6.1. Kinora respects intellectual property rights, does not authorise use of the site to infringe them, and responds to rights-holder notices. If you are a rights holder or are authorised and believe that accessible material affects you, write to contact@kinora.com.co with the subject “Kinora – Copyright”.',
      '6.2. The notice must include: (a) the notifier’s name, position, address, telephone number and email, and the identification of the person represented, if acting for another; (b) identification of the protected work; (c) the exact URL or precise location of the challenged material; (d) a good-faith statement that authorisation is lacking; (e) a statement of accuracy and standing; and (f) a physical or electronic signature.',
      '6.3. Kinora will review complete notices and, in principle within the following five (5) business days, remove, de-index or disable access to the challenged material, without admitting liability. Additional information may be requested if the notice is incomplete.',
      '6.4. Kinora does not host the works: definitive deletion of the file can only be carried out by whoever hosts it. Where possible, Kinora will forward the complaint to the relevant provider, and the rights holder may also contact that provider directly.',
      '6.5. Counter-notice. Anyone who considers a removal mistaken may request review at the same email address, subject “Kinora – Review”, identifying the material and explaining the reasons. Kinora may restore the material if the notice proves unfounded.',
      '6.6. Notices known to be false or misleading may give rise to liability.',
      '6.7. Kinora may suspend integration with sources in respect of which repeated well-founded notices are received.'
    ]
  },
  {
    id: 'ip',
    title: '7. Site intellectual property and attributions',
    body: [
      '7.1. The Kinora brand, logo, interface design, proprietary code, original texts, compilation and other elements created by the Operator are protected by applicable intellectual and industrial property laws.',
      '7.2. Their reproduction, distribution, public communication or transformation without prior written authorisation is prohibited, except as permitted by law (legitimate quotations, authorised uses).',
      '7.3. Rights over audiovisual works, studio trademarks, posters, images and third-party metadata belong to their holders. Third-party trademarks are mentioned for identification purposes.',
      '7.4. This product uses the TMDB API but is not endorsed or certified by TMDB. TMDB data and images are displayed in accordance with its terms of use. See the Annex.',
      '7.5. Users acquire no rights over the software, design or brand merely by using the site.'
    ]
  },
  {
    id: 'ads',
    title: '8. Advertising and third-party services',
    body: [
      '8.1. The site may display advertisements from third-party ad networks. These may use cookies, identifiers or similar technologies in accordance with their policies. Consent management is explained in the Privacy Policy (section 8).',
      '8.2. Kinora is not responsible for the content of advertisements or for transactions or relationships that users establish with advertisers.',
      '8.3. Advertising supports the free nature of the service. Ad blockers are compatible, although they may affect measurement.',
      '8.4. Integration of analytics, subtitles, players or other external services is also governed by the terms and policies of those providers.'
    ]
  },
  {
    id: 'subtitles',
    title: '9. Subtitles, audio labels and language',
    body: [
      '9.1. Subtitles, where they exist, come from third parties or automated processes. They may be out of sync, incomplete, poorly translated or absent. Kinora does not guarantee their quality.',
      '9.2. “Subtitled” or “dubbed” labels are approximate and derived from heuristics, not from per-title verification. A work labelled as dubbed may play with subtitles, and vice versa, depending on the source available at the time.',
      '9.3. The language of the page and the language of the audio may differ. Language preferences apply to the extent that sources allow.',
      '9.4. Kinora does not guarantee the existence of a specific version (language, dubbing, subtitles, quality or resolution).'
    ]
  },
  {
    id: 'adult',
    title: '10. Adult content and ratings',
    body: [
      '10.1. The catalogue may include works with themes, violence, language or images intended for adult audiences. Ratings or warnings come from third parties, are informative and are not guaranteed. There is no effective age verification.',
      '10.2. It is up to the user, and to legal representatives in the case of minors, to decide which content is appropriate.'
    ]
  },
  {
    id: 'availability',
    title: '11. Availability, maintenance and technical limitations',
    body: [
      '11.1. The service is offered “as is” and “as available”, without guarantee of any result.',
      '11.2. Kinora does not warrant that the service will be uninterrupted, error-free, completely secure or compatible with every device, browser or connection.',
      '11.3. Maintenance, provider failures, network blocks, geographic restrictions or capacity limits may affect the experience.',
      '11.4. Kinora may apply rate limits, caches and anti-abuse mechanisms, and may temporarily suspend access for users or networks that compromise stability.'
    ]
  },
  {
    id: 'liability',
    title: '12. Disclaimer and limitation of liability',
    body: [
      '12.1. To the maximum extent permitted by law, Kinora, its Operator, collaborators and providers will not be liable for: (a) indirect damages, loss of profit, loss of data, indirect consequential damage or reputational harm; (b) Third-Party Content, its quality, legality or availability, including advertisements, pop-ups, redirects or software; (c) user decisions based on catalogue information; (d) interruptions, loss of locally stored lists or preferences, or playback failures; (e) third-party attacks, force majeure or events beyond reasonable control; (f) use of the site in violation of the law or these Terms; (g) the accuracy of audio labels, subtitles, ratings or metadata; or (h) content hosted by third parties and the legality of sources in each country.',
      '12.2. Where the law does not allow total exclusion, liability will be limited, to the maximum extent permitted, to amounts paid directly to Kinora for the service in the twelve (12) months preceding the event. As the service is free, liability will be limited to the mandatory legal minimum.',
      '12.3. Nothing excludes or limits liability for wilful misconduct or gross negligence, nor non-waivable warranties or consumer rights where applicable.',
      '12.4. Unless a different legal period applies, any claim must be brought within two (2) years of the event giving rise to it.'
    ]
  },
  {
    id: 'indemnity',
    title: '13. Indemnity',
    body: [
      'The user will indemnify Kinora against claims, penalties, costs and damages arising from: (i) misuse of the service; (ii) breach of these Terms; (iii) infringement of third-party rights; (iv) use of Third-Party Content contrary to law; or (v) content or conduct attributable to the user, to the extent permitted by law.'
    ]
  },
  {
    id: 'data',
    title: '14. Data protection and cookies',
    body: [
      'Data processing and the use of cookies are governed by the Privacy Policy, which forms an integral part of the relationship with the user. It identifies the Controller, explains the purposes, the rights of data subjects, the cookie inventory and how to exercise those rights.'
    ]
  },
  {
    id: 'changes',
    title: '15. Amendments',
    body: [
      '15.1. Kinora may update these Terms. The current version will be published with its date and version number; material changes will be announced with a visible notice.',
      '15.2. Continued use after publication constitutes acceptance, unless the law requires specific consent. Changes concerning personal data are governed by the Privacy Policy.'
    ]
  },
  {
    id: 'termination',
    title: '16. Suspension and termination',
    body: [
      'Kinora may deny, restrict or terminate access immediately, without prejudice to other actions, where there is non-compliance, legal or technical risk, or a requirement from an authority. Provisions that by their nature should survive (intellectual property, limitation of liability, indemnity and governing law) will remain in force.'
    ]
  },
  {
    id: 'law',
    title: '17. Governing law and jurisdiction',
    body: [
      '17.1. These Terms are governed by the laws of the Republic of Colombia, without prejudice to mandatory consumer protection rules applicable to the user according to their residence.',
      '17.2. For disputes, the parties submit to the competent judges and courts of Colombia in accordance with the applicable competence rules. Where consumer legislation grants the user a special non-waivable forum, that forum will prevail.',
      '17.3. For consumer protection and personal data matters, the user may approach the Superintendence of Industry and Commerce under the terms established by law.'
    ]
  },
  {
    id: 'contact',
    title: '18. Contact',
    body: [
      'Operator: Kinora (identified by brand, domain and email). Website: https://kinora.com.co. Email: contact@kinora.com.co.',
      'Suggested subjects: “Kinora – Legal”, “Kinora – Copyright”, “Kinora – Privacy”.',
      'Kinora may communicate through notices on the site or, if the user has written, to the email address from which they wrote.'
    ]
  },
  {
    id: 'general',
    title: '19. General provisions',
    body: [
      '19.1. If any clause is declared void or unenforceable, the remainder will remain in force. 19.2. Failure to exercise a right does not imply waiver. 19.3. These Terms are the entire agreement on use of the site and replace prior understandings, without prejudice to the Privacy Policy and specific notices. 19.4. Headings are for convenience and do not affect interpretation. 19.5. These Terms are drawn up in Spanish; if there are translations, the Spanish version prevails. 19.6. Neither party is liable for non-performance due to force majeure or unforeseeable events. 19.7. Kinora may assign these Terms to a successor in the operation of the site; the user may not assign them without written authorisation. 19.8. The version history is published in the Privacy Policy (Annex IV) and in this section when it changes.'
    ]
  },
  {
    id: 'annex',
    title: 'Annex — Attributions',
    body: [
      'Metadata and images: This product uses the TMDB API but is not endorsed or certified by TMDB. Posters, synopses and data belong to their respective holders.',
      'Trademarks and studios: logos and names of studios, platforms and works are used for identification purposes.',
      'Video, subtitle, advertising and trailer providers: credited where their integration requires it, in the site footer.',
      'End of document.'
    ]
  }
];

export default function Terms() {
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
          <span className="terms__kicker">Legal</span>
          <h1>Terms of Service</h1>
          <p>
            The rules for using Kinora: what the service is, what it is not, how third-party content works, and how to
            reach us. Written to be read, not to be skipped.
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
          </nav>
        </aside>

        <article className="terms__content">
          {SECTIONS.map(section => (
            <section key={section.id} id={section.id} className="terms__section">
              <h2>{section.title}</h2>
              {section.body.map((paragraph, index) => (
                <p key={index}>{paragraph}</p>
              ))}
            </section>
          ))}

          <div className="terms__end">
            <p>Questions about these Terms?</p>
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
          <a href="/privacy.html">Privacy Policy</a>
          <a href="/">Home</a>
        </span>
      </footer>
    </div>
  );
}
