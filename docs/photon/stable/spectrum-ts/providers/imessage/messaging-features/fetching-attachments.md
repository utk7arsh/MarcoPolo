##### Fetching iMessage attachments

Source: https://photon.codes/docs/spectrum-ts/providers/imessage/messaging-features/fetching-attachments.md
Documentation version: Stable

Retrieve an attachment by its iMessage GUID using `getAttachment` on the
narrowed platform instance. The returned
`Attachment` is
lazy. `.read()` and `.stream()` each trigger an independent download, so cache
`.read()` if you need the bytes more than once.

```ts
import { imessage } from "spectrum-ts/providers/imessage";

const im = imessage(app);
const att = await im.getAttachment("p:0/GUID");

if (att) {
  console.log(att.name, att.mimeType, att.size);
  const bytes = await att.read();
}
```

In multi-phone mode, pass the phone number as the second argument to route the
request through the correct instance:

```ts
const att = await im.getAttachment("p:0/GUID", "+15559999999");
```

When only one phone is configured, or in shared-pool mode, the phone parameter
is optional.

  `getAttachment` requires `@spectrum-ts/imessage`. With
  `@spectrum-ts/imessage-local`, it throws an
  `UnsupportedError`.
  Local inbound attachments are still available through each incoming
  message's content.


