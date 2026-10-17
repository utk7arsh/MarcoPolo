##### iMessage group membership

Source: https://photon.codes/docs/spectrum-ts/providers/imessage/messaging-features/group-membership.md
Documentation version: Stable

Add or remove members with `space.add()` / `space.remove()`, or leave the group
with `space.leave()` — or use the canonical `addMember()` / `removeMember()` /
`leaveSpace()` content builders:

```ts
import { addMember, leaveSpace, removeMember } from "spectrum-ts";

// Sugar
await space.add("+15553333333");
await space.add([alice, "carol@example.com"]); // batches land in one call
await space.remove("+15553333333");
await space.leave();

// Canonical
await space.send(addMember("+15553333333"));
await space.send(removeMember("+15553333333"));
await space.send(leaveSpace());
```

Members are E.164 phone numbers or emails — the same handles `space.create`
accepts.

List the current roster with `space.getMembers()`. Each entry's `id` is the
canonical address, so the results feed straight back into `add()` / `remove()`
/ `space.create()`; the agent's own number is excluded:

```ts
import { imessage } from "spectrum-ts/providers/imessage";

const members = await space.getMembers();
await space.remove(members.filter((member) => member.id.endsWith("@example.com")));

// Typed extras (address/country/service) via the narrowed instance
const im = imessage(app);
const detailed = await im.getMembers(space);
for (const member of detailed) {
  console.log(member.address, member.service);
}
```

Membership management requires `@spectrum-ts/imessage` and only works on group
chats. With `@spectrum-ts/imessage-local`, or on a DM, it throws an
`UnsupportedError` — a DM cannot be converted into a group, so create a new
group with `space.create` instead. `getMembers()` has the same constraints.


