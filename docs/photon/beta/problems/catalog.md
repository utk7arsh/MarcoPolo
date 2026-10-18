> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Catalog

> Problem types from the deployed API and the published shared error registry.

export function ProblemsTable() {
  const CDN = 'https://esm.sh/@tanstack/table-core@8.21.3';
  const [core, setCore] = useState(null);
  const [problems, setProblems] = useState([]);
  const [sorting, setSorting] = useState([{
    id: 'slug',
    desc: false
  }]);
  const [query, setQuery] = useState('');
  const [group, setGroup] = useState('All');
  const [target, setTarget] = useState(null);
  useEffect(() => {
    if (window.__photonTableCore) {
      setCore(window.__photonTableCore);
      return;
    }
    const id = '__photon_table_core_loader';
    const done = () => setCore(window.__photonTableCore ?? null);
    window.addEventListener('photon-table-core', done);
    if (!document.getElementById(id)) {
      const el = document.createElement('script');
      el.id = id;
      el.type = 'module';
      el.textContent = `
        try {
          const m = await import(${JSON.stringify(CDN)})
          window.__photonTableCore = m
        } catch { window.__photonTableCore = null }
        window.dispatchEvent(new Event('photon-table-core'))
      `;
      document.head.appendChild(el);
    }
    return () => window.removeEventListener('photon-table-core', done);
  }, []);
  const headers = useMemo(() => [{
    key: 'slug',
    label: 'Type'
  }, {
    key: 'code',
    label: 'Code'
  }, {
    key: 'status',
    label: 'Status'
  }], []);
  const columns = useMemo(() => [...headers.map(h => ({
    accessorKey: h.key
  })), {
    accessorKey: 'group'
  }, {
    accessorKey: 'description'
  }], [headers]);
  const groups = useMemo(() => ['All', ...[...new Set(problems.map(p => p.group))]], [problems]);
  const filtered = useMemo(() => group === 'All' ? problems : problems.filter(p => p.group === group), [problems, group]);
  const table = useMemo(() => {
    if (!core) return null;
    const instance = core.createTable({
      data: filtered,
      columns,
      state: {},
      onStateChange: () => {},
      renderFallbackValue: null,
      getCoreRowModel: core.getCoreRowModel(),
      getSortedRowModel: core.getSortedRowModel(),
      getFilteredRowModel: core.getFilteredRowModel(),
      globalFilterFn: 'includesString'
    });
    return instance;
  }, [core, filtered, columns]);
  if (table) {
    table.setOptions(prev => ({
      ...prev,
      data: filtered,
      state: {
        ...prev.state,
        sorting,
        globalFilter: query
      },
      onSortingChange: setSorting,
      onGlobalFilterChange: setQuery
    }));
  }
  const localRows = useMemo(() => {
    const needle = query.trim().toLowerCase();
    const rows = filtered.filter(p => !needle || `${p.slug} ${p.code} ${p.description} ${p.group} ${p.status}`.toLowerCase().includes(needle));
    const {id, desc} = sorting[0] ?? ({
      id: 'slug',
      desc: false
    });
    rows.sort((a, b) => id === 'status' ? parseInt(a.status, 10) - parseInt(b.status, 10) || a.slug.localeCompare(b.slug) : String(a[id]).localeCompare(String(b[id])));
    return desc ? rows.reverse() : rows;
  }, [filtered, query, sorting]);
  const rows = table ? table.getRowModel().rows.map(r => r.original) : localRows;
  useEffect(() => {
    const staticTable = document.getElementById('problems-static');
    if (!staticTable) return;
    const rows = [...staticTable.querySelectorAll('tbody tr')].map(tr => {
      const cell = [...tr.children].map(td => (td.textContent ?? '').trim());
      if (cell.length < 5 || !cell[0]) return null;
      return {
        slug: cell[0],
        code: cell[1],
        status: cell[2],
        group: cell[3],
        description: cell[4]
      };
    }).filter(Boolean);
    if (rows.length === 0) return;
    staticTable.querySelectorAll('[id]').forEach(anchor => anchor.removeAttribute('id'));
    setProblems(rows);
    staticTable.hidden = true;
  }, []);
  useEffect(() => {
    const revealFromHash = () => {
      const slug = decodeURIComponent((window.location.hash || '').replace(/^#/, ''));
      if (!slug) return;
      setQuery('');
      setGroup('All');
      setTarget(slug);
      requestAnimationFrame(() => {
        const row = document.getElementById(slug);
        if (row) row.scrollIntoView({
          block: 'center',
          behavior: 'smooth'
        });
      });
    };
    revealFromHash();
    window.addEventListener('hashchange', revealFromHash);
    return () => window.removeEventListener('hashchange', revealFromHash);
  }, []);
  const toggleSort = id => {
    setSorting(([current] = {}) => current && current.id === id ? [{
      id,
      desc: !current.desc
    }] : [{
      id,
      desc: false
    }]);
  };
  const arrowFor = id => {
    const active = sorting[0];
    if (!active || active.id !== id) return '';
    return active.desc ? '↓' : '↑';
  };
  return <div className="pt-catalogue w-full max-w-full contain-[inline-size]">
      <div className="pt-controls">
        <input className="pt-search" type="search" value={query} placeholder={problems.length ? `Search ${problems.length} problems by type, code, status, or group` : 'Search problems'} onChange={e => setQuery(e.target.value)} aria-label="Search problems" />
        <select className="pt-group" value={group} onChange={e => setGroup(e.target.value)} aria-label="Filter by group">
          {groups.map(g => <option key={g} value={g}>{g}</option>)}
        </select>
      </div>

      <div className="pt-scroll">
        <table className="pt-table">
          <thead>
            <tr>
              {headers.map(col => <th key={col.key} className="pt-sortable" onClick={() => toggleSort(col.key)} aria-sort={sorting[0]?.id === col.key ? sorting[0].desc ? 'descending' : 'ascending' : 'none'}>
                  {col.label}
                  <span className="pt-arrow">{arrowFor(col.key)}</span>
                </th>)}
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(p => <tr key={p.slug} id={p.slug} className={p.slug === target ? 'pt-row pt-target' : 'pt-row'}>
                <td><code>{p.slug}</code></td>
                <td><code>{p.code}</code></td>
                <td><code className={String(p.status).split(',').some(status => Number(status.trim()) >= 500) ? 'pt-5xx' : 'pt-4xx'}>{p.status}</code></td>
                <td>{p.description}</td>
              </tr>)}
          </tbody>
        </table>
      </div>

      {rows.length === 0 && <p className="pt-empty">{`No problem matches “${query}”.`}</p>}
      {rows.length > 0 && <p className="pt-count">{`Showing ${rows.length} of ${problems.length} problems.`}</p>}
    </div>;
}

<ProblemsTable />

<div id="problems-static">
  | Type | Code | Status | Group | Description |
  | - | - | - | - | - |
  | <span id="account-closing">`account-closing`</span> | `ACCOUNT_CLOSING` | `409` | Account and access | Account Is Closing. |
  | <span id="account-deleted">`account-deleted`</span> | `ACCOUNT_DELETED` | `410` | Account and access | Account Deleted. |
  | <span id="account-not-found">`account-not-found`</span> | `ACCOUNT_NOT_FOUND` | `404` | Account and access | Account Not Found. |
  | <span id="account-owns-organizations">`account-owns-organizations`</span> | `ACCOUNT_OWNS_ORGANIZATIONS` | `409` | Account and access | Account Owns Organizations. |
  | <span id="account-service-key-limit-reached">`account-service-key-limit-reached`</span> | `ACCOUNT_SERVICE_KEY_LIMIT_REACHED` | `409` | Account and access | Account Service Key Limit Reached. |
  | <span id="account-service-key-not-found">`account-service-key-not-found`</span> | `ACCOUNT_SERVICE_KEY_NOT_FOUND` | `404` | Account and access | Account Service Key Not Found. |
  | <span id="already-exists">`already-exists`</span> | `ALREADY_EXISTS` | `409` | Generic | Already Exists. Any endpoint may return this problem. |
  | <span id="api-key-limit-reached">`api-key-limit-reached`</span> | `API_KEY_LIMIT_REACHED` | `409` | Other | API Key Limit Reached. |
  | <span id="api-key-not-found">`api-key-not-found`</span> | `API_KEY_NOT_FOUND` | `404` | Other | API Key Not Found. |
  | <span id="api-key-revoked">`api-key-revoked`</span> | `API_KEY_REVOKED` | `409` | Other | API Key Revoked. |
  | <span id="app-installation-assertion-invalid">`app-installation-assertion-invalid`</span> | `APP_INSTALLATION_ASSERTION_INVALID` | `401` | Other | Invalid Installation Client Assertion. |
  | <span id="app-installation-assertion-replayed">`app-installation-assertion-replayed`</span> | `APP_INSTALLATION_ASSERTION_REPLAYED` | `409` | Other | Installation Assertion Already Used. |
  | <span id="app-installation-config-changed">`app-installation-config-changed`</span> | `APP_INSTALLATION_CONFIG_CHANGED` | `409` | Other | Installation App Configuration Changed. |
  | <span id="app-installation-config-not-found">`app-installation-config-not-found`</span> | `APP_INSTALLATION_CONFIG_NOT_FOUND` | `404` | Other | App Installation Configuration Not Found. |
  | <span id="app-installation-config-unavailable">`app-installation-config-unavailable`</span> | `APP_INSTALLATION_CONFIG_UNAVAILABLE` | `409` | Other | App Installation Configuration Unavailable. |
  | <span id="app-installation-config-version-conflict">`app-installation-config-version-conflict`</span> | `APP_INSTALLATION_CONFIG_VERSION_CONFLICT` | `409` | Other | App Installation Configuration Version Conflict. |
  | <span id="app-installation-delivery-unavailable">`app-installation-delivery-unavailable`</span> | `APP_INSTALLATION_DELIVERY_UNAVAILABLE` | `409` | Other | Installation Delivery Unavailable. |
  | <span id="app-installation-managed">`app-installation-managed`</span> | `APP_INSTALLATION_MANAGED` | `409` | Other | App Installation Managed. |
  | <span id="app-installation-not-found">`app-installation-not-found`</span> | `APP_INSTALLATION_NOT_FOUND` | `404` | Other | Installation Not Found. |
  | <span id="app-installation-permissions-invalid">`app-installation-permissions-invalid`</span> | `APP_INSTALLATION_PERMISSIONS_INVALID` | `400` | Other | Installation Permissions Invalid. |
  | <span id="app-installation-redirect-uri-invalid">`app-installation-redirect-uri-invalid`</span> | `APP_INSTALLATION_REDIRECT_URI_INVALID` | `409` | Other | App Installation Redirect URI Invalid. |
  | <span id="app-installation-repair-unavailable">`app-installation-repair-unavailable`</span> | `APP_INSTALLATION_REPAIR_UNAVAILABLE` | `409` | Other | Installation Repair Unavailable. |
  | <span id="app-installation-request-already-bound">`app-installation-request-already-bound`</span> | `APP_INSTALLATION_REQUEST_ALREADY_BOUND` | `409` | Other | App Installation Request Already Bound. |
  | <span id="app-installation-request-not-found">`app-installation-request-not-found`</span> | `APP_INSTALLATION_REQUEST_NOT_FOUND` | `404` | Other | App Installation Request Not Found. |
  | <span id="app-installation-state-conflict">`app-installation-state-conflict`</span> | `APP_INSTALLATION_STATE_CONFLICT` | `409` | Other | Installation State Conflict. |
  | <span id="app-installation-version-conflict">`app-installation-version-conflict`</span> | `APP_INSTALLATION_VERSION_CONFLICT` | `409` | Other | Installation Version Conflict. |
  | <span id="assignment-exists">`assignment-exists`</span> | `ASSIGNMENT_EXISTS` | `409` | Platforms and lines | Assignment Exists. |
  | <span id="assignment-not-found">`assignment-not-found`</span> | `ASSIGNMENT_NOT_FOUND` | `404` | Platforms and lines | Assignment Not Found. |
  | <span id="attachment-conflict">`attachment-conflict`</span> | `ATTACHMENT_CONFLICT` | `409` | Messaging resources | Attachment Conflict. |
  | <span id="attachment-not-found">`attachment-not-found`</span> | `ATTACHMENT_NOT_FOUND` | `404` | Messaging resources | Attachment Not Found. |
  | <span id="attachment-not-ready">`attachment-not-ready`</span> | `ATTACHMENT_NOT_READY` | `409` | Messaging resources | Attachment Not Ready. |
  | <span id="attachment-upload-not-ready">`attachment-upload-not-ready`</span> | `ATTACHMENT_UPLOAD_NOT_READY` | `409` | Messaging resources | Attachment Upload Not Ready. |
  | <span id="billing-entitlements-pending">`billing-entitlements-pending`</span> | `BILLING_ENTITLEMENTS_PENDING` | `503` | Projects and billing | Billing Entitlements Pending. |
  | <span id="billing-not-provisioned">`billing-not-provisioned`</span> | `BILLING_NOT_PROVISIONED` | `503` | Projects and billing | Billing Not Provisioned. |
  | <span id="billing-suspended">`billing-suspended`</span> | `BILLING_SUSPENDED` | `402` | Projects and billing | Billing Suspended. |
  | <span id="captcha-required">`captcha-required`</span> | `CAPTCHA_REQUIRED` | `403` | Account and access | Captcha Required. Adds `challengeContext`, `provider`, `siteKey`. |
  | <span id="email-domain-already-connected">`email-domain-already-connected`</span> | `EMAIL_DOMAIN_ALREADY_CONNECTED` | `409` | Platforms and lines | Email Domain Already Connected. |
  | <span id="email-domain-cap-exceeded">`email-domain-cap-exceeded`</span> | `EMAIL_DOMAIN_CAP_EXCEEDED` | `409` | Platforms and lines | Email Domain Cap Exceeded. |
  | <span id="entitlement-required">`entitlement-required`</span> | `ENTITLEMENT_REQUIRED` | `402` | Projects and billing | Entitlement Required. Adds `effectiveAt`, `reason`. Any endpoint may return this problem. |
  | <span id="failed-precondition">`failed-precondition`</span> | `FAILED_PRECONDITION` | `409` | Generic | Failed Precondition. Any endpoint may return this problem. |
  | <span id="forbidden">`forbidden`</span> | `FORBIDDEN` | `403` | Generic | Forbidden. Any endpoint may return this problem. |
  | <span id="http-error">`http-error`</span> | `HTTP_ERROR` | `400` | Generic | Request Failed. Any endpoint may return this problem. |
  | <span id="idempotency-key-invalid">`idempotency-key-invalid`</span> | `IDEMPOTENCY_KEY_INVALID` | `400` | Idempotency | Idempotency Key Invalid. Any endpoint may return this problem. |
  | <span id="idempotency-key-required">`idempotency-key-required`</span> | `IDEMPOTENCY_KEY_REQUIRED` | `400` | Idempotency | Idempotency Key Required. Any endpoint may return this problem. |
  | <span id="idempotency-key-reused">`idempotency-key-reused`</span> | `IDEMPOTENCY_KEY_REUSED` | `422` | Idempotency | Idempotency Key Reused. Any endpoint may return this problem. |
  | <span id="idempotency-request-in-progress">`idempotency-request-in-progress`</span> | `IDEMPOTENCY_REQUEST_IN_PROGRESS` | `409` | Idempotency | Idempotency Request In Progress. Any endpoint may return this problem. |
  | <span id="idempotency-response-unsupported">`idempotency-response-unsupported`</span> | `IDEMPOTENCY_RESPONSE_UNSUPPORTED` | `500` | Idempotency | Idempotency Response Unsupported. Any endpoint may return this problem. |
  | <span id="idempotency-unavailable">`idempotency-unavailable`</span> | `IDEMPOTENCY_UNAVAILABLE` | `503` | Idempotency | Idempotency Unavailable. Any endpoint may return this problem. |
  | <span id="imessage-mode-dedicated">`imessage-mode-dedicated`</span> | `IMESSAGE_MODE_DEDICATED` | `409` | Platforms and lines | iMessage Mode Is Dedicated. |
  | <span id="insufficient-scope">`insufficient-scope`</span> | `INSUFFICIENT_SCOPE` | `403` | Other | Insufficient Scope. |
  | <span id="internal-error">`internal-error`</span> | `INTERNAL_ERROR` | `500` | Generic | Internal Server Error. Any endpoint may return this problem. |
  | <span id="invalid-argument">`invalid-argument`</span> | `INVALID_ARGUMENT` | `400` | Request and validation | Invalid Argument. Any endpoint may return this problem. |
  | <span id="invalid-attachment-request">`invalid-attachment-request`</span> | `INVALID_ATTACHMENT_REQUEST` | `400` | Messaging resources | Invalid Attachment Request. |
  | <span id="invalid-auth-context">`invalid-auth-context`</span> | `INVALID_AUTH_CONTEXT` | `500` | Generic | Invalid Authentication Context. Any endpoint may return this problem. |
  | <span id="invalid-content">`invalid-content`</span> | `INVALID_CONTENT` | `422` | Other | Invalid Content. Adds `issues`. |
  | <span id="invalid-page-token">`invalid-page-token`</span> | `INVALID_PAGE_TOKEN` | `400` | Other | Invalid Page Token. |
  | <span id="invalid-request">`invalid-request`</span> | `INVALID_REQUEST` | `400` | Other | Invalid Request. |
  | <span id="invalid-return-to">`invalid-return-to`</span> | `INVALID_RETURN_TO` | `400` | Other | Invalid Return To. |
  | <span id="invitation-email-mismatch">`invitation-email-mismatch`</span> | `INVITATION_EMAIL_MISMATCH` | `403` | Other | Invitation Email Mismatch. |
  | <span id="invitation-expired">`invitation-expired`</span> | `INVITATION_EXPIRED` | `409` | Other | Invitation Expired. |
  | <span id="invitation-inviter-ineligible">`invitation-inviter-ineligible`</span> | `INVITATION_INVITER_INELIGIBLE` | `403` | Other | Invitation Inviter Ineligible. |
  | <span id="invitation-not-found">`invitation-not-found`</span> | `INVITATION_NOT_FOUND` | `404` | Other | Invitation Not Found. |
  | <span id="invitation-predates-removal">`invitation-predates-removal`</span> | `INVITATION_PREDATES_REMOVAL` | `409` | Other | Invitation Predates Removal. |
  | <span id="invitation-revoked">`invitation-revoked`</span> | `INVITATION_REVOKED` | `409` | Other | Invitation Revoked. |
  | <span id="invitation-role-conflict">`invitation-role-conflict`</span> | `INVITATION_ROLE_CONFLICT` | `409` | Other | Invitation Role Conflict. |
  | <span id="invitation-terminal">`invitation-terminal`</span> | `INVITATION_TERMINAL` | `409` | Other | Invitation Terminal. |
  | <span id="limit-reached">`limit-reached`</span> | `LIMIT_REACHED` | `409` | Generic | Limit Reached. Any endpoint may return this problem. |
  | <span id="message-not-found">`message-not-found`</span> | `MESSAGE_NOT_FOUND` | `404` | Messaging resources | Message Not Found. |
  | <span id="message-not-readable">`message-not-readable`</span> | `MESSAGE_NOT_READABLE` | `409` | Messaging resources | Message Not Readable. |
  | <span id="message-too-long">`message-too-long`</span> | `MESSAGE_TOO_LONG` | `422` | Messaging resources | Message Too Long. |
  | <span id="mfa-already-enrolled">`mfa-already-enrolled`</span> | `MFA_ALREADY_ENROLLED` | `409` | Other | MFA Already Enrolled. |
  | <span id="mfa-enrollment-expired">`mfa-enrollment-expired`</span> | `MFA_ENROLLMENT_EXPIRED` | `410` | Other | MFA Enrollment Expired. |
  | <span id="mfa-enrollment-invalid">`mfa-enrollment-invalid`</span> | `MFA_ENROLLMENT_INVALID` | `400` | Other | MFA Enrollment Invalid. |
  | <span id="mfa-factor-not-found">`mfa-factor-not-found`</span> | `MFA_FACTOR_NOT_FOUND` | `404` | Other | MFA Factor Not Found. |
  | <span id="mfa-verification-failed">`mfa-verification-failed`</span> | `MFA_VERIFICATION_FAILED` | `422` | Other | MFA Verification Failed. |
  | <span id="not-authenticated">`not-authenticated`</span> | `NOT_AUTHENTICATED` | `401` | Generic | Not Authenticated. Any endpoint may return this problem. |
  | <span id="not-found">`not-found`</span> | `NOT_FOUND` | `404` | Generic | Not Found. Any endpoint may return this problem. |
  | <span id="oauth-client-creation-conflict">`oauth-client-creation-conflict`</span> | `OAUTH_CLIENT_CREATION_CONFLICT` | `409` | Account and access | OAuth Client Creation Conflict. |
  | <span id="oauth-client-deletion-conflict">`oauth-client-deletion-conflict`</span> | `OAUTH_CLIENT_DELETION_CONFLICT` | `409` | Account and access | OAuth Client Deletion Conflict. |
  | <span id="oauth-client-not-found">`oauth-client-not-found`</span> | `OAUTH_CLIENT_NOT_FOUND` | `404` | Account and access | OAuth Client Not Found. |
  | <span id="oauth-client-precondition-failed">`oauth-client-precondition-failed`</span> | `OAUTH_CLIENT_PRECONDITION_FAILED` | `412` | Account and access | OAuth Client Precondition Failed. |
  | <span id="oauth-client-quota-exceeded">`oauth-client-quota-exceeded`</span> | `OAUTH_CLIENT_QUOTA_EXCEEDED` | `429` | Account and access | OAuth Client Quota Exceeded. |
  | <span id="oauth-secret-configured">`oauth-secret-configured`</span> | `OAUTH_SECRET_CONFIGURED` | `409` | Account and access | OAuth Secret Already Configured. |
  | <span id="oauth-secret-creation-conflict">`oauth-secret-creation-conflict`</span> | `OAUTH_SECRET_CREATION_CONFLICT` | `409` | Account and access | OAuth Secret Creation Conflict. |
  | <span id="oauth-secret-not-configured">`oauth-secret-not-configured`</span> | `OAUTH_SECRET_NOT_CONFIGURED` | `409` | Account and access | OAuth Secret Not Configured. |
  | <span id="oauth-secret-revocation-conflict">`oauth-secret-revocation-conflict`</span> | `OAUTH_SECRET_REVOCATION_CONFLICT` | `409` | Account and access | OAuth Secret Revocation Conflict. |
  | <span id="operation-not-cancellable">`operation-not-cancellable`</span> | `OPERATION_NOT_CANCELLABLE` | `409` | Projects and billing | Operation Not Cancellable. |
  | <span id="operation-not-found">`operation-not-found`</span> | `OPERATION_NOT_FOUND` | `404` | Projects and billing | Operation Not Found. |
  | <span id="operation-unavailable">`operation-unavailable`</span> | `OPERATION_UNAVAILABLE` | `422` | Projects and billing | Operation Unavailable. |
  | <span id="organization-auth-policy-changed">`organization-auth-policy-changed`</span> | `ORGANIZATION_AUTH_POLICY_CHANGED` | `409` | Other | Organization Authentication Policy Changed. |
  | <span id="organization-closure-blocked">`organization-closure-blocked`</span> | `CLOSURE_BLOCKED` | `409` | Other | Organization Closure Blocked. |
  | <span id="organization-connection-not-found">`organization-connection-not-found`</span> | `ORGANIZATION_CONNECTION_NOT_FOUND` | `404` | Other | Organization Connection Not Found. |
  | <span id="organization-member-not-found">`organization-member-not-found`</span> | `ORGANIZATION_MEMBER_NOT_FOUND` | `404` | Other | Organization Member Not Found. |
  | <span id="organization-member-removed">`organization-member-removed`</span> | `ORGANIZATION_MEMBER_REMOVED` | `409` | Other | Organization Member Removed. |
  | <span id="organization-membership-version-conflict">`organization-membership-version-conflict`</span> | `ORGANIZATION_MEMBERSHIP_VERSION_CONFLICT` | `409` | Other | Organization Membership Version Conflict. |
  | <span id="organization-owner-invariant">`organization-owner-invariant`</span> | `ORGANIZATION_OWNER_INVARIANT` | `409` | Other | Organization Ownership Requires Recovery. |
  | <span id="organization-owner-protected">`organization-owner-protected`</span> | `ORGANIZATION_OWNER_PROTECTED` | `409` | Other | Organization Owner Protected. |
  | <span id="organization-recovery-required">`organization-recovery-required`</span> | `ORGANIZATION_RECOVERY_REQUIRED` | `409` | Other | Organization Recovery Required. |
  | <span id="organization-self-management-forbidden">`organization-self-management-forbidden`</span> | `ORGANIZATION_SELF_MANAGEMENT_FORBIDDEN` | `409` | Other | Use Leave Organization. |
  | <span id="organization-sso-conflict">`organization-sso-conflict`</span> | `ORGANIZATION_SSO_CONFLICT` | `409` | Other | Organization SSO Conflict. |
  | <span id="organization-sso-enabled">`organization-sso-enabled`</span> | `ORGANIZATION_SSO_ENABLED` | `409` | Other | Organization SSO Enabled. |
  | <span id="organization-sso-not-found">`organization-sso-not-found`</span> | `ORGANIZATION_SSO_NOT_FOUND` | `404` | Other | Organization SSO Not Found. |
  | <span id="organization-sso-precondition-failed">`organization-sso-precondition-failed`</span> | `ORGANIZATION_SSO_PRECONDITION_FAILED` | `412` | Other | Organization SSO Precondition Failed. |
  | <span id="organization-sso-required">`organization-sso-required`</span> | `ORGANIZATION_SSO_REQUIRED` | `403` | Other | Organization SSO Required. |
  | <span id="organization-sync-unavailable">`organization-sync-unavailable`</span> | `ORGANIZATION_SYNC_UNAVAILABLE` | `409` | Other | Organization Synchronization Unavailable. |
  | <span id="organization-transfer-to-self">`organization-transfer-to-self`</span> | `ORGANIZATION_TRANSFER_TO_SELF` | `409` | Other | Choose Another Organization Owner. |
  | <span id="organization-unavailable">`organization-unavailable`</span> | `ORGANIZATION_UNAVAILABLE` | `409` | Other | Organization Unavailable. |
  | <span id="organization-version-conflict">`organization-version-conflict`</span> | `ORGANIZATION_VERSION_CONFLICT` | `409` | Other | Organization Version Conflict. |
  | <span id="payload-too-large">`payload-too-large`</span> | `PAYLOAD_TOO_LARGE` | `413` | Request and validation | Payload Too Large. Any endpoint may return this problem. |
  | <span id="payment-provider-not-ready">`payment-provider-not-ready`</span> | `PAYMENT_PROVIDER_NOT_READY` | `503` | Projects and billing | Payment Provider Not Ready. |
  | <span id="project-closing">`project-closing`</span> | `PROJECT_CLOSING` | `409` | Projects and billing | Project Is Closing. |
  | <span id="project-deleted">`project-deleted`</span> | `PROJECT_DELETED` | `410` | Projects and billing | Project Deleted. |
  | <span id="project-not-found">`project-not-found`</span> | `PROJECT_NOT_FOUND` | `404` | Projects and billing | Project Not Found. |
  | <span id="query-concurrency-limit">`query-concurrency-limit`</span> | `QUERY_CONCURRENCY_LIMIT` | `429` | Other | Query Concurrency Limit. Any endpoint may return this problem. |
  | <span id="query-resource-limit">`query-resource-limit`</span> | `QUERY_RESOURCE_LIMIT` | `422` | Other | Query Resource Limit. Any endpoint may return this problem. |
  | <span id="rate-limited">`rate-limited`</span> | `RATE_LIMITED` | `429` | Request and validation | Too Many Requests. Any endpoint may return this problem. |
  | <span id="request-timeout">`request-timeout`</span> | `REQUEST_TIMEOUT` | `504` | Request and validation | Request Timeout. Any endpoint may return this problem. |
  | <span id="resource-deleted">`resource-deleted`</span> | `RESOURCE_DELETED` | `410` | Generic | Resource Deleted. Any endpoint may return this problem. |
  | <span id="resource-mismatch">`resource-mismatch`</span> | `RESOURCE_MISMATCH` | `403` | Generic | Resource Mismatch. Any endpoint may return this problem. |
  | <span id="resource-not-found">`resource-not-found`</span> | `RESOURCE_NOT_FOUND` | `404` | Generic | Resource Not Found. |
  | <span id="route-not-found">`route-not-found`</span> | `ROUTE_NOT_FOUND` | `404` | Generic | Route Not Found. Any endpoint may return this problem. |
  | <span id="sender-not-found">`sender-not-found`</span> | `SENDER_NOT_FOUND` | `404` | Other | Sender Not Found. |
  | <span id="sender-not-sendable">`sender-not-sendable`</span> | `SENDER_NOT_SENDABLE` | `409` | Other | Sender Not Sendable. |
  | <span id="service-credential-conflict">`service-credential-conflict`</span> | `SERVICE_CREDENTIAL_CONFLICT` | `409` | Upstream | Service Credential Conflict. |
  | <span id="service-credential-not-found">`service-credential-not-found`</span> | `SERVICE_CREDENTIAL_NOT_FOUND` | `404` | Upstream | Service Credential Not Found. |
  | <span id="service-credential-precondition-failed">`service-credential-precondition-failed`</span> | `SERVICE_CREDENTIAL_PRECONDITION_FAILED` | `412` | Upstream | Service Credential Precondition Failed. |
  | <span id="service-identity-not-found">`service-identity-not-found`</span> | `SERVICE_IDENTITY_NOT_FOUND` | `404` | Upstream | Service Identity Not Found. |
  | <span id="service-identity-version-conflict">`service-identity-version-conflict`</span> | `SERVICE_IDENTITY_VERSION_CONFLICT` | `409` | Upstream | Service Identity Version Conflict. |
  | <span id="shared-line-cap-exceeded">`shared-line-cap-exceeded`</span> | `SHARED_LINE_CAP_EXCEEDED` | `409` | Platforms and lines | Shared Line Cap Exceeded. |
  | <span id="shared-line-group-unsupported">`shared-line-group-unsupported`</span> | `SHARED_LINE_GROUP_UNSUPPORTED` | `422` | Platforms and lines | Shared Line Group Unsupported. |
  | <span id="shared-line-inbound-required">`shared-line-inbound-required`</span> | `SHARED_LINE_INBOUND_REQUIRED` | `403` | Platforms and lines | Shared Line Inbound Required. |
  | <span id="shared-line-not-assigned">`shared-line-not-assigned`</span> | `SHARED_LINE_NOT_ASSIGNED` | `403` | Platforms and lines | Shared Line Not Assigned. |
  | <span id="shared-line-pool-exhausted">`shared-line-pool-exhausted`</span> | `SHARED_LINE_POOL_EXHAUSTED` | `503` | Platforms and lines | Shared Line Pool Exhausted. |
  | <span id="slug-taken">`slug-taken`</span> | `SLUG_TAKEN` | `409` | Other | Slug Already Taken. Adds `suggestion`. |
  | <span id="sms-campaign-capacity-exceeded">`sms-campaign-capacity-exceeded`</span> | `SMS_CAMPAIGN_CAPACITY_EXCEEDED` | `409` | Other | Campaign number capacity exhausted. |
  | <span id="sms-campaign-context-unavailable">`sms-campaign-context-unavailable`</span> | `SMS_CAMPAIGN_CONTEXT_UNAVAILABLE` | `503` | Other | Campaign context unavailable. |
  | <span id="sms-campaign-invalid-request">`sms-campaign-invalid-request`</span> | `SMS_CAMPAIGN_INVALID_REQUEST` | `400` | Other | Invalid SMS campaign request. |
  | <span id="sms-campaign-mutation-in-progress">`sms-campaign-mutation-in-progress`</span> | `SMS_CAMPAIGN_MUTATION_IN_PROGRESS` | `409` | Other | Assignment mutation in progress. Adds `operationId`, `operationUrl`. |
  | <span id="sms-campaign-not-eligible">`sms-campaign-not-eligible`</span> | `SMS_CAMPAIGN_NOT_ELIGIBLE` | `409` | Other | SMS Campaign Not Eligible. |
  | <span id="sms-campaign-not-found">`sms-campaign-not-found`</span> | `SMS_CAMPAIGN_NOT_FOUND` | `404` | Other | Campaign not found. |
  | <span id="sms-campaign-not-ready">`sms-campaign-not-ready`</span> | `SMS_CAMPAIGN_NOT_READY` | `409` | Other | Campaign not ready. |
  | <span id="sms-campaign-organization-mismatch">`sms-campaign-organization-mismatch`</span> | `SMS_CAMPAIGN_ORGANIZATION_MISMATCH` | `403` | Other | Campaign belongs to another organization. |
  | <span id="sms-campaign-reconciliation-required">`sms-campaign-reconciliation-required`</span> | `SMS_CAMPAIGN_RECONCILIATION_REQUIRED` | `409` | Other | Campaign reconciliation required. |
  | <span id="sms-campaign-version-conflict">`sms-campaign-version-conflict`</span> | `SMS_CAMPAIGN_VERSION_CONFLICT` | `409` | Other | Assignment version conflict. |
  | <span id="sms-line-not-found">`sms-line-not-found`</span> | `SMS_LINE_NOT_FOUND` | `404` | Other | SMS line not found. |
  | <span id="sms-line-unsupported">`sms-line-unsupported`</span> | `SMS_LINE_UNSUPPORTED` | `409` | Other | SMS line unsupported. |
  | <span id="space-ambiguous">`space-ambiguous`</span> | `SPACE_AMBIGUOUS` | `409` | Messaging resources | Multiple Matching Spaces. |
  | <span id="space-not-found">`space-not-found`</span> | `SPACE_NOT_FOUND` | `404` | Messaging resources | Space Not Found. |
  | <span id="space-not-sendable">`space-not-sendable`</span> | `SPACE_NOT_SENDABLE` | `409` | Messaging resources | Space Not Sendable. |
  | <span id="space-requires-owned-agent">`space-requires-owned-agent`</span> | `SPACE_REQUIRES_OWNED_AGENT` | `422` | Messaging resources | Space Requires Owned Agent. |
  | <span id="sso-subscription-required">`sso-subscription-required`</span> | `SSO_SUBSCRIPTION_REQUIRED` | `412` | Other | SSO Subscription Required. |
  | <span id="telegram-project-deleted">`telegram-project-deleted`</span> | `TELEGRAM_PROJECT_DELETED` | `409` | Other | Telegram Project Deleted. |
  | <span id="telegram-provision-in-progress">`telegram-provision-in-progress`</span> | `TELEGRAM_PROVISION_IN_PROGRESS` | `409` | Other | Telegram Provision In Progress. Adds `operationId`, `operationUrl`. |
  | <span id="unsupported-content">`unsupported-content`</span> | `UNSUPPORTED_CONTENT` | `422` | Other | Unsupported Content. |
  | <span id="upstream-failure">`upstream-failure`</span> | `UPSTREAM_FAILURE` | `502` | Upstream | Upstream Service Failure. Any endpoint may return this problem. |
  | <span id="upstream-timeout">`upstream-timeout`</span> | `UPSTREAM_TIMEOUT` | `504` | Upstream | Upstream Service Timeout. Any endpoint may return this problem. |
  | <span id="upstream-unavailable">`upstream-unavailable`</span> | `UPSTREAM_UNAVAILABLE` | `503` | Upstream | Upstream Service Unavailable. Any endpoint may return this problem. |
  | <span id="user-identity-conflict">`user-identity-conflict`</span> | `USER_IDENTITY_CONFLICT` | `409` | Messaging resources | User Identity Conflict. |
  | <span id="user-not-found">`user-not-found`</span> | `USER_NOT_FOUND` | `404` | Messaging resources | User Not Found. |
  | <span id="validation-failed">`validation-failed`</span> | `VALIDATION_FAILED` | `422` | Request and validation | Request Validation Failed. Adds `issues`. Any endpoint may return this problem. |
  | <span id="voice-default-profile-assignment-forbidden">`voice-default-profile-assignment-forbidden`</span> | `VOICE_DEFAULT_PROFILE_ASSIGNMENT_FORBIDDEN` | `409` | Voice | Voice Default Profile Assignment Forbidden. |
  | <span id="voice-default-profile-deletion-forbidden">`voice-default-profile-deletion-forbidden`</span> | `VOICE_DEFAULT_PROFILE_DELETION_FORBIDDEN` | `409` | Voice | Voice Default Profile Deletion Forbidden. |
  | <span id="voice-default-profile-exists">`voice-default-profile-exists`</span> | `VOICE_DEFAULT_PROFILE_EXISTS` | `409` | Voice | Voice Default Profile Exists. |
  | <span id="voice-default-profile-required">`voice-default-profile-required`</span> | `VOICE_DEFAULT_PROFILE_REQUIRED` | `409` | Voice | Voice Default Profile Required. |
  | <span id="voice-outbound-configured">`voice-outbound-configured`</span> | `VOICE_OUTBOUND_CONFIGURED` | `409` | Voice | Voice Outbound Already Configured. |
  | <span id="voice-outbound-not-configured">`voice-outbound-not-configured`</span> | `VOICE_OUTBOUND_NOT_CONFIGURED` | `409` | Voice | Voice Outbound Not Configured. |
  | <span id="voice-outbound-operation-pending">`voice-outbound-operation-pending`</span> | `VOICE_OUTBOUND_OPERATION_PENDING` | `409` | Voice | Voice Outbound Operation Pending. |
  | <span id="voice-profile-direction-configured">`voice-profile-direction-configured`</span> | `VOICE_PROFILE_DIRECTION_CONFIGURED` | `409` | Voice | Voice Profile Direction Configured. |
  | <span id="voice-profile-in-use">`voice-profile-in-use`</span> | `VOICE_PROFILE_IN_USE` | `409` | Voice | Voice Profile In Use. |
  | <span id="voice-profile-not-found">`voice-profile-not-found`</span> | `VOICE_PROFILE_NOT_FOUND` | `404` | Voice | Voice Profile Not Found. |
  | <span id="voice-profile-version-conflict">`voice-profile-version-conflict`</span> | `VOICE_PROFILE_VERSION_CONFLICT` | `409` | Voice | Voice Profile Version Conflict. |
  | <span id="webhook-destination-deleted">`webhook-destination-deleted`</span> | `WEBHOOK_DESTINATION_DELETED` | `410` | Webhooks | Webhook Destination Deleted. |
  | <span id="webhook-destination-not-found">`webhook-destination-not-found`</span> | `WEBHOOK_DESTINATION_NOT_FOUND` | `404` | Webhooks | Webhook Destination Not Found. |
  | <span id="whatsapp-account-disconnecting">`whatsapp-account-disconnecting`</span> | `WHATSAPP_ACCOUNT_DISCONNECTING` | `409` | WhatsApp | WhatsApp Business Account Disconnecting. |
  | <span id="whatsapp-account-provisioning">`whatsapp-account-provisioning`</span> | `WHATSAPP_ACCOUNT_PROVISIONING` | `409` | WhatsApp | WhatsApp Business Account Has Provisioning Numbers. |
  | <span id="whatsapp-display-name-unavailable">`whatsapp-display-name-unavailable`</span> | `WHATSAPP_DISPLAY_NAME_UNAVAILABLE` | `422` | WhatsApp | WhatsApp Display Name Unavailable. |
  | <span id="whatsapp-mode-dedicated">`whatsapp-mode-dedicated`</span> | `WHATSAPP_MODE_DEDICATED` | `409` | WhatsApp | WhatsApp Mode Is Dedicated. |
  | <span id="whatsapp-sender-connected">`whatsapp-sender-connected`</span> | `WHATSAPP_SENDER_CONNECTED` | `409` | WhatsApp | WhatsApp Sender Connected. |
  | <span id="whatsapp-sender-provisioning">`whatsapp-sender-provisioning`</span> | `WHATSAPP_SENDER_PROVISIONING` | `409` | WhatsApp | WhatsApp Sender Provisioning. |
  | <span id="whatsapp-verification-code-not-found">`whatsapp-verification-code-not-found`</span> | `WHATSAPP_VERIFICATION_CODE_NOT_FOUND` | `404` | WhatsApp | WhatsApp Verification Code Not Found. |
  | <span id="whatsapp-verification-window-expired">`whatsapp-verification-window-expired`</span> | `WHATSAPP_VERIFICATION_WINDOW_EXPIRED` | `422` | WhatsApp | WhatsApp Verification Window Expired. |
  | <span id="whatsapp-voip-source-not-eligible">`whatsapp-voip-source-not-eligible`</span> | `WHATSAPP_VOIP_SOURCE_NOT_ELIGIBLE` | `404` | WhatsApp | WhatsApp VoIP Source Not Eligible. |
  | <span id="whatsapp-voip-source-releasing">`whatsapp-voip-source-releasing`</span> | `WHATSAPP_VOIP_SOURCE_RELEASING` | `409` | WhatsApp | WhatsApp VoIP Source Releasing. |
  | <span id="whatsapp-waba-not-connected">`whatsapp-waba-not-connected`</span> | `WHATSAPP_WABA_NOT_CONNECTED` | `404` | WhatsApp | WhatsApp Business Account Not Connected. |
</div>

### onboarding-completed

This problem type is no longer declared in the current schema.


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.