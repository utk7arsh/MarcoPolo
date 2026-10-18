> ## Documentation Index
> Fetch the complete documentation index at: https://docs.photon.codes/docs/llms.txt
> Use this file to discover all available pages before exploring further.

> ## Agent Instructions
> Use Stable documentation by default. Honor an explicit Beta request or a URL under /docs/beta/. If the requested version conflicts with the installed CLI package or API origin, clarify the target before writing integration code.
> Pages under /docs/beta/ document Beta; other product pages document Stable. Keep the CLI package, commands, API origin, and credentials within the selected version. State the documentation version in your answer.
> For MCP search, always pass version: Stable or version: Beta. Unfiltered search mixes both versions. For filesystem reads, keep Beta queries under /beta/ and exclude /beta/ from Stable queries; discover paths before reading them.
> The public docs base is https://photon.codes/docs. Convert MCP page paths to public URLs under that base, preserving /beta/ when present. Read https://photon.codes/docs/skill.md for version selection and https://photon.codes/docs/llms.txt for the version indexes.

# Event reference

> The generated Socket.IO event and acknowledgement contract.

The AsyncAPI document defines incoming commands, outgoing events, and acknowledgement shapes. Its messages describe Socket.IO argument tuples; use a Socket.IO client to encode the transport packets.

<Card title="Download the AsyncAPI contract" icon="download" href="https://api.photon.codes/asyncapi.yaml">
  Download the generated event contract.
</Card>

The schema is generated from runtime definitions and checked for drift. Behavioral tests separately check sequencing, replay, limits, and cleanup. See [Start a session](/docs/beta/websocket/session) and [Cursors and replay](/docs/beta/websocket/cursors) for those obligations.


## AsyncAPI

````yaml https://api.photon.codes/asyncapi.yaml Root
id: Root
title: Event Delivery
description: ''
servers:
  - id: event-delivery
    protocol: wss
    host: api.photon.codes
    bindings: []
    variables:
      - id: projectId
        description: The project to subscribe to.
        defaultValue: YOUR_PROJECT_ID
        allowedValues: []
        examples: []
address: /
parameters: []
bindings:
  - protocol: ws
    version: 0.1.0
    value:
      headers:
        properties:
          connection:
            const: Upgrade
            type: string
          upgrade:
            const: websocket
            type: string
        type: object
      method: GET
      query:
        externalDocs:
          description: Engine.IO Protocol
          url: https://socket.io/docs/v4/engine-io-protocol/
        properties:
          EIO:
            const: '4'
            description: The version of the protocol
            type: string
          sid:
            description: The session identifier
            type: string
          transport:
            description: The name of the transport
            enum:
              - websocket
            type: string
        required:
          - EIO
          - transport
        type: object
    schemaProperties:
      - name: headers
        type: object
        required: false
        properties:
          - name: connection
            type: string
            description: Upgrade
            required: false
          - name: upgrade
            type: string
            description: websocket
            required: false
      - name: method
        type: string
        description: GET
        required: false
      - name: query
        type: object
        required: false
        properties:
          - name: EIO
            type: string
            description: The version of the protocol
            required: true
          - name: sid
            type: string
            description: The session identifier
            required: false
          - name: transport
            type: string
            description: The name of the transport
            enumValues:
              - websocket
            required: true
operations:
  - &ref_9
    id: RootRecvOperationReply
    title: reply
    description: Incoming event reply
    type: receive
    messages:
      - &ref_13
        id: rootIncomingReply
        contentType: text/plain
        payload:
          - items: &ref_0
              not:
                x-parser-schema-id: <anonymous-schema-9>
              x-parser-schema-id: <anonymous-schema-8>
            maxItems: 1
            minItems: 1
            prefixItems: &ref_1
              - additionalProperties: false
                properties:
                  body:
                    description: Standard base64 response body, padded or unpadded.
                    pattern: >-
                      ^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}(?:==)?|[A-Za-z0-9+/]{3}=?)?$
                    type: string
                  errorReason:
                    type: string
                  eventId:
                    minLength: 1
                    type: string
                  headers:
                    additionalProperties:
                      type: string
                    propertyNames:
                      type: string
                    type: object
                  status:
                    anyOf:
                      - const: 0
                        type: number
                      - maximum: 599
                        minimum: 100
                        type: integer
                required:
                  - eventId
                type: object
            type: array
            x-parser-schema-id: <anonymous-schema-7>
            name: reply
        headers: []
        jsonPayloadSchema:
          items: *ref_0
          maxItems: 1
          minItems: 1
          prefixItems: *ref_1
          type: array
          x-parser-schema-id: <anonymous-schema-7>
        title: reply
        example: '{}'
        bindings: []
        extensions:
          - id: x-parser-unique-object-id
            value: rootIncomingReply
    bindings: []
    extensions: &ref_4
      - id: x-parser-unique-object-id
        value: Root
  - &ref_10
    id: RootRecvOperationSubscribe
    title: subscribe
    description: Incoming event subscribe
    type: receive
    messages:
      - &ref_14
        id: rootIncomingSubscribe
        contentType: text/plain
        payload:
          - items: &ref_2
              not:
                x-parser-schema-id: <anonymous-schema-12>
              x-parser-schema-id: <anonymous-schema-11>
            maxItems: 1
            minItems: 1
            prefixItems: &ref_3
              - additionalProperties: false
                properties:
                  apiVersion:
                    description: >-
                      Customer event contract date to pin for this subscription.
                      Omit to use the server default. The date must be
                      selectable by the server; unsupported dates are rejected.
                      Send it again when resubscribing after reconnect.
                    format: date
                    pattern: >-
                      ^(?:(?:\d\d[2468][048]|\d\d[13579][26]|\d\d0[48]|[02468][048]00|[13579][26]00)-02-29|\d{4}-(?:(?:0[13578]|1[02])-(?:0[1-9]|[12]\d|3[01])|(?:0[469]|11)-(?:0[1-9]|[12]\d|30)|(?:02)-(?:0[1-9]|1\d|2[0-8])))$
                    type: string
                  startSeq:
                    description: >-
                      0 starts live; a positive cursor resumes after that
                      sequence.
                    maximum: 9007199254740991
                    minimum: 0
                    type: integer
                required:
                  - startSeq
                type: object
            type: array
            x-parser-schema-id: <anonymous-schema-10>
            name: subscribe
        headers: []
        jsonPayloadSchema:
          items: *ref_2
          maxItems: 1
          minItems: 1
          prefixItems: *ref_3
          type: array
          x-parser-schema-id: <anonymous-schema-10>
        title: subscribe
        example: '{}'
        bindings: []
        extensions:
          - id: x-parser-unique-object-id
            value: rootIncomingSubscribe
    bindings: []
    extensions: *ref_4
  - &ref_11
    id: RootSendOperationDelivery
    title: delivery
    description: Outgoing event delivery
    type: send
    messages:
      - &ref_15
        id: rootOutgoingDelivery
        contentType: text/plain
        payload:
          - items: &ref_5
              not:
                x-parser-schema-id: <anonymous-schema-15>
              x-parser-schema-id: <anonymous-schema-14>
            maxItems: 2
            minItems: 2
            prefixItems: &ref_6
              - allOf:
                  - additionalProperties: {}
                    properties:
                      id:
                        minLength: 1
                        type: string
                      type:
                        minLength: 1
                        type: string
                    required:
                      - id
                      - type
                    type: object
                  - additionalProperties: {}
                    propertyNames:
                      type: string
                    type: object
              - additionalProperties: false
                properties:
                  replyExpected:
                    type: boolean
                  seq:
                    maximum: 9007199254740991
                    minimum: 0
                    type: integer
                required:
                  - seq
                  - replyExpected
                type: object
            type: array
            x-parser-schema-id: <anonymous-schema-13>
            name: delivery
        headers: []
        jsonPayloadSchema:
          items: *ref_5
          maxItems: 2
          minItems: 2
          prefixItems: *ref_6
          type: array
          x-parser-schema-id: <anonymous-schema-13>
        title: delivery
        example: '{}'
        bindings: []
        extensions:
          - id: x-parser-unique-object-id
            value: rootOutgoingDelivery
    bindings: []
    extensions: *ref_4
  - &ref_12
    id: RootSendOperationDeliveryError
    title: delivery_error
    description: Outgoing event delivery_error
    type: send
    messages:
      - &ref_16
        id: rootOutgoingDeliveryError
        contentType: text/plain
        payload:
          - items: &ref_7
              not:
                x-parser-schema-id: <anonymous-schema-18>
              x-parser-schema-id: <anonymous-schema-17>
            maxItems: 1
            minItems: 1
            prefixItems: &ref_8
              - additionalProperties: false
                properties:
                  code:
                    enum:
                      - protocol_violation
                      - subscribe_timeout
                      - frame_too_large
                      - slow_consumer
                      - capacity
                      - server_draining
                      - upstream_unavailable
                      - internal
                      - reply_unknown_event
                      - reply_invalid
                      - reply_too_large
                      - reply_publish_failed
                      - reply_capacity
                      - reply_forbidden
                      - subscribe_repeated
                      - frame_invalid
                    type: string
                  eventId:
                    type: string
                  fatal:
                    type: boolean
                  message:
                    type: string
                  reason:
                    type: string
                  retryAfterMs:
                    exclusiveMinimum: 0
                    maximum: 9007199254740991
                    type: integer
                  retryable:
                    type: boolean
                required:
                  - code
                  - message
                  - fatal
                  - retryable
                type: object
            type: array
            x-parser-schema-id: <anonymous-schema-16>
            name: delivery_error
        headers: []
        jsonPayloadSchema:
          items: *ref_7
          maxItems: 1
          minItems: 1
          prefixItems: *ref_8
          type: array
          x-parser-schema-id: <anonymous-schema-16>
        title: delivery_error
        example: '{}'
        bindings: []
        extensions:
          - id: x-parser-unique-object-id
            value: rootOutgoingDeliveryError
    bindings: []
    extensions: *ref_4
sendOperations:
  - *ref_9
  - *ref_10
receiveOperations:
  - *ref_11
  - *ref_12
sendMessages:
  - *ref_13
  - *ref_14
receiveMessages:
  - *ref_15
  - *ref_16
extensions:
  - id: x-parser-unique-object-id
    value: Root
securitySchemes:
  - id: projectApiKey
    name: projectApiKey
    type: http
    description: >-
      Enter your complete project API key (`pho_sk_...`) without the `Bearer `
      prefix. It is sent as `Authorization: Bearer <project API key>`. The key
      must belong to the `projectId` in the connection URL.
    scheme: bearer
    extensions: []

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.