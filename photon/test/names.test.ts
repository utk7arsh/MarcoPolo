import assert from "node:assert/strict";
import { test } from "node:test";
import { extractName, isDontKnow } from "../src/names.js";

test("extractName pulls the item out of captions and transcripts", () => {
  const cases: Array<[string, string | null]> = [
    ["cumin", "cumin"],
    ["That's the cumin, love.", "cumin"],
    ["these are Dad's reading glasses", "reading glasses"],
    ["Dad's keys", "keys"],
    ["It's the TV remote", "TV remote"],
    ["this jar is paprika", "paprika"],
    ["the one on the left is paprika", "paprika"],
    ["This is the cumin that grandma brought from India", "cumin"],
    ["Paprika - the smoked one", "Paprika"],
    ["no wait, it's cumin", "cumin"],
    ["Um, that's your blood pressure monitor 🙂", "blood pressure monitor"],
    ["Here are your house keys!", "house keys"],
    ["it", null],
    ["", null],
  ];
  for (const [input, expected] of cases) assert.equal(extractName(input), expected, input);
});

test("isDontKnow recognizes a caretaker who is not sure", () => {
  for (const s of ["I don't know", "dunno", "no idea, sorry", "Not sure", "idk"]) assert.ok(isDontKnow(s), s);
  for (const s of ["cumin", "no wait, it's cumin", "Dad's keys"]) assert.ok(!isDontKnow(s), s);
});
