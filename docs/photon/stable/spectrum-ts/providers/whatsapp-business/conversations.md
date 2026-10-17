##### WhatsApp Business conversations

Source: https://photon.codes/docs/spectrum-ts/providers/whatsapp-business/conversations.md
Documentation version: Stable

WhatsApp Business supports 1:1 conversations. The provider rejects group creation explicitly.

###### Starting a conversation

Resolve a user by their WhatsApp phone number in international format with digits only, then open a 1:1 space:

```ts
const wa = whatsappBusiness(app);
const customer = await wa.user("15551234567");
const space = await wa.space.create(customer);

await space.send("Thanks for reaching out.");
```

Passing more than one user to `space.create()` throws.


#### Telegram

