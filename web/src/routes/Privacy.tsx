import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Languages } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { ThemeToggle } from "../components/ThemeToggle";

/* Every statement here describes what the code actually does (docs/WEB-APP-DESIGN.md, section 12B maps each claim to
   the code and test behind it). If behaviour changes, change this text and bump POLICY_VERSION in api/app/policy.py. */

const Section = ({ id, title, children }: { id: string; title: string; children: ReactNode }) => (
  <section aria-labelledby={id} className="mt-10">
    <h2 id={id} className="text-lg font-semibold tracking-tight text-slate-900">{title}</h2>
    <div className="mt-3 space-y-3 text-[15px] leading-relaxed text-slate-700">{children}</div>
  </section>
);

const Th = ({ children }: { children: ReactNode }) => <th className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-600">{children}</th>;
const Td = ({ children, strong }: { children: ReactNode; strong?: boolean }) => (
  <td className={`px-3 py-2.5 align-top ${strong ? "font-medium text-slate-900" : ""}`}>{children}</td>
);

export default function Privacy() {
  const { user } = useAuth();
  const meta = useQuery({ queryKey: ["meta"], queryFn: api.meta, staleTime: Infinity });
  const contact = meta.data?.privacy_contact;
  const version = meta.data?.policy_version;

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-surface">
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between px-4">
          <Link to={user ? "/settings" : "/login"} className="flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900">
            <ArrowLeft aria-hidden className="size-4" />
            {user ? "Back to the app" : "Back to sign in"}
          </Link>
          <div className="flex items-center gap-2">
            <span className="flex items-center gap-2 text-sm font-semibold tracking-tight text-slate-900">
              <span className="flex size-7 items-center justify-center rounded-md bg-brand-600 text-white"><Languages aria-hidden className="size-4" /></span>
              Language Tutor
            </span>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Privacy Policy</h1>
        <p className="mt-2 text-sm text-slate-500">
          {version ? <>Version {version}. </> : null}Written in plain language.
        </p>

        <div className="mt-6 rounded-xl border border-brand-200 bg-brand-50 p-4 text-[15px] text-brand-900 dark:border-brand-800 dark:bg-brand-900/40 dark:text-brand-100">
          <p className="font-semibold">In short</p>
          <ul className="mt-2 list-disc space-y-1 pl-5">
            <li>The only personal information we ask for is your <strong>name</strong> and your <strong>email address</strong>.</li>
            <li>We use them to run your account, and for nothing else. No advertising, no tracking, no selling.</li>
            <li>You can download everything we hold about you, or delete it all, any time in <strong>Settings</strong>.</li>
          </ul>
        </div>

        <Section id="who" title="1. Who this applies to">
          <p>
            This policy explains how Language Tutor (“the app”) handles your personal information. The app is run by the
            person or organisation that installed it (“the operator”), not by a large company.{" "}
            {contact ? <>You can contact the operator at <a className="text-brand-600 underline dark:text-brand-200" href={`mailto:${contact}`}>{contact}</a>.</> : <>For questions about your data, contact the person who gave you access to this app.</>}
          </p>
        </Section>

        <Section id="collect" title="2. What we collect">
          <p>
            Your <strong>name</strong> and <strong>email address</strong> are the only information that identifies you.
            Everything else in the table is either something you choose to type in, or a technical record needed to keep
            you signed in.
          </p>
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="w-full text-sm">
              <caption className="sr-only">Information the app stores</caption>
              <thead className="border-b border-slate-200 bg-slate-100/60"><tr><Th>Information</Th><Th>What it is used for</Th></tr></thead>
              <tbody className="divide-y divide-slate-100">
                <tr><Td strong>Your name</Td><Td>The name you enter at sign-up. Shown in the app so it can greet you. You can change it.</Td></tr>
                <tr><Td strong>Your email address</Td><Td>How you sign in, and the way the operator can contact you about your account. You can change it.</Td></tr>
                <tr><Td strong>Your password</Td><Td>Stored only as a scrambled one-way hash. Nobody, including the operator, can read it.</Td></tr>
                <tr><Td strong>Words, meanings and stories you add</Td><Td>To run the learning features. This is your own study material.</Td></tr>
                <tr><Td strong>The languages you study</Td><Td>To show the right word list.</Td></tr>
                <tr><Td strong>Sign-in records</Td><Td>When each sign-in started and when it ends, plus a random code. Used to keep you signed in and to let you sign out of every device. Removed when you sign out or they expire.</Td></tr>
                <tr><Td strong>Proof you accepted this policy</Td><Td>The date, and which version of this policy, you accepted when you signed up.</Td></tr>
              </tbody>
            </table>
          </div>
          <p>We do <strong>not</strong> collect your phone number, address, date of birth, location, payment details, or advertising identifiers.</p>
        </Section>

        <Section id="use" title="3. How we use it">
          <p>
            Only to provide the app: to create your account, sign you in, greet you by name, keep your words separate from
            everyone else’s, let you download or delete your data, and protect accounts (for example, by pausing sign-in after
            repeated wrong passwords).
          </p>
          <p>
            We do not use your information for advertising or profiling, we do not sell it, and no decisions about you are made
            automatically. The app does not send you any email at the moment. If that ever changes (for example, to reset a
            forgotten password), the email will only be about your account, and this policy will be updated first.
          </p>
        </Section>

        <Section id="cookies" title="4. Cookies and browser storage">
          <p>
            The app sets <strong>one cookie</strong>, which keeps you signed in. It is strictly necessary, cannot be read by
            page scripts, and lasts until you sign out or up to 8 hours. There are no analytics, advertising or third-party cookies.
          </p>
          <p>
            Your browser also remembers your light/dark choice and your selected language on your own device. These are never
            sent to the server.
          </p>
        </Section>

        <Section id="sharing" title="5. Who we share it with">
          <p>We do not sell or give your information to anyone for their own purposes. Two things to know:</p>
          <ul className="list-disc space-y-1.5 pl-5">
            <li>
              <strong>AI features.</strong> Chat and Story Studio are not available yet. When they are, the words and messages you
              type are sent to an AI service (Groq) so it can write a reply or story. Your name and email address are
              <strong> not</strong> sent.
            </li>
            <li>
              <strong>Where it is stored.</strong> Your information lives in a database run by the operator. If the law requires
              it, the operator may have to disclose information to the authorities.
            </li>
          </ul>
        </Section>

        <Section id="keep" title="6. How long we keep it">
          <p>
            Until you delete your account. Deleting your account (Settings → Delete account) permanently removes your name, email,
            password hash, words, languages and sign-in records straight away. The app itself keeps no backups. If the operator
            makes database backups, deleted information can remain in them until they expire; ask the operator how long.
          </p>
        </Section>

        <Section id="rights" title="7. Your choices and rights">
          <ul className="list-disc space-y-1.5 pl-5">
            <li><strong>See and take your data:</strong> Settings → Data &amp; privacy → Download my data (a file you can open or move elsewhere).</li>
            <li><strong>Correct it:</strong> change your name, email or password in Settings.</li>
            <li><strong>Delete it:</strong> Settings → Delete account.</li>
            <li><strong>Withdraw consent:</strong> you can delete your account at any time. Nothing is held back.</li>
          </ul>
          <p>
            Depending on where you live (for example under the EU/UK GDPR or California law) you may have further rights, such as
            asking the operator to restrict how your data is used, or complaining to your local data protection authority.
            Contact the operator to use them.
          </p>
        </Section>

        <Section id="security" title="8. How we protect it">
          <p>
            Passwords are stored as hashes. Each account can only reach its own data, and this is tested automatically. Signing out
            ends the sign-in on the server, and you can end every sign-in at once. Repeated wrong passwords temporarily lock sign-in.
            No system is perfectly secure. Whoever runs the app is responsible for serving it over HTTPS whenever it is reachable
            over a network.
          </p>
        </Section>

        <Section id="children" title="9. Children">
          <p>The app is not meant for children under 16. If you are younger, please ask a parent or guardian before creating an account.</p>
        </Section>

        <Section id="changes" title="10. Changes to this policy">
          <p>
            When this policy changes in a way that matters, the version above changes. When you sign up, the app records which
            version you accepted.
          </p>
        </Section>

        <Section id="contact" title="11. Contact">
          <p>{contact ? <>Questions or requests: <a className="text-brand-600 underline dark:text-brand-200" href={`mailto:${contact}`}>{contact}</a>.</> : <>Questions or requests: contact the person who runs this installation of the app.</>}</p>
        </Section>
      </main>
    </div>
  );
}
