const ADMIN_PASSWORD_HASH = "b56d3612d0d068d682f999050bf06b611e17811df27e593af35c7cd184d8d3c6";
const STORAGE_KEY = "scscp_data_v1";
const ADMIN_KEY = "scscp_admin_v1";
const NAME_EDIT_KEY = "scscp_name_edit_v1";

// To generate a new hash in the browser console:
// await crypto.subtle.digest("SHA-256", new TextEncoder().encode("your-password"))
//   .then(buf => Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, "0")).join(""));

const makeCall = (
  callName,
  meaning = "Declare the current combat state without narration.",
  context = "",
  whenToUse = ["Call once, clearly, within the same breath."],
  responseExpected = "Acknowledge only if protocol requires follow-up.",
  notes = ""
) => ({
  callName,
  category: "",
  context,
  meaning,
  whenToUse,
  responseExpected,
  notes,
});

const DEFAULT_DATA = [
  {
    category: "TEAM LEAD (INTENT)",
    calls: [
      { ...makeCall("Forward", "Move the team forward on the current line."), category: "TEAM LEAD (INTENT)" },
      { ...makeCall("Target", "Assign or update the primary target focus."), category: "TEAM LEAD (INTENT)" },
      { ...makeCall("Target out", "Drop the current target from focus."), category: "TEAM LEAD (INTENT)" },
      { ...makeCall("Regroup on", "Re-center on the anchor while staying engaged or ready to re-engage."), category: "TEAM LEAD (INTENT)" },
      { ...makeCall("Reset", "Disengage and reset the fight state (break contact)."), category: "TEAM LEAD (INTENT)" },
      { ...makeCall("Hold", "Maintain current position and spacing."), category: "TEAM LEAD (INTENT)" },
    ],
  },
  {
    category: "REGROUP RESPONSES",
    calls: [
      { ...makeCall("Distance", "Report regroup distance from anchor."), category: "REGROUP RESPONSES" },
      { ...makeCall("Ready", "Confirm regroup complete and ready to act."), category: "REGROUP RESPONSES" },
    ],
  },
  {
    category: "PILOT PERSONAL THREAT",
    calls: [
      { ...makeCall("Aggro", "You are being focused or pressured by threat."), category: "PILOT PERSONAL THREAT" },
      { ...makeCall("Evasive", "Actively evading incoming threat."), category: "PILOT PERSONAL THREAT" },
      { ...makeCall("Low boost", "Boost reserve is low; evasive options limited."), category: "PILOT PERSONAL THREAT" },
      { ...makeCall("Clear", "Threat pressure is off or no longer on you."), category: "PILOT PERSONAL THREAT" },
      { ...makeCall("Red (PERSONAL)", "Critical health; fragile but not necessarily about to die."), category: "PILOT PERSONAL THREAT" },
    ],
  },
  {
    category: "TEAM GEOMETRY",
    calls: [
      { ...makeCall("Ball in", "Team geometry tightens or collapses inward."), category: "TEAM GEOMETRY" },
      { ...makeCall("Ball out", "Team geometry spreads or expands outward."), category: "TEAM GEOMETRY" },
    ],
  },
  {
    category: "ATTACHMENT",
    calls: [
      { ...makeCall("With", "You are attached to a teammate or target path."), category: "ATTACHMENT" },
      { ...makeCall("With pilot", "You are attached to a specific pilot."), category: "ATTACHMENT" },
    ],
  },
  {
    category: "TARGET AWARENESS",
    calls: [
      { ...makeCall("Looking", "Searching for target contact."), category: "TARGET AWARENESS" },
      { ...makeCall("No contact", "Target not in sight or sensors."), category: "TARGET AWARENESS" },
      { ...makeCall("Seen", "Target is visually confirmed."), category: "TARGET AWARENESS" },
    ],
  },
  {
    category: "DISTANCE SCALE",
    calls: [
      { ...makeCall("Five clicks", "Distance reference: five clicks."), category: "DISTANCE SCALE" },
      { ...makeCall("Three clicks", "Distance reference: three clicks."), category: "DISTANCE SCALE" },
      { ...makeCall("Two clicks", "Distance reference: two clicks."), category: "DISTANCE SCALE" },
      { ...makeCall("One click", "Distance reference: one click."), category: "DISTANCE SCALE" },
    ],
  },
  {
    category: "ENGAGEMENT EFFECTIVENESS",
    calls: [
      { ...makeCall("Merging", "Closing to merge with the target."), category: "ENGAGEMENT EFFECTIVENESS" },
      { ...makeCall("Effective", "Current engagement is landing as intended."), category: "ENGAGEMENT EFFECTIVENESS" },
      { ...makeCall("Very effective", "Engagement is decisively effective."), category: "ENGAGEMENT EFFECTIVENESS" },
      { ...makeCall("Not effective", "Engagement is not landing; adjust."), category: "ENGAGEMENT EFFECTIVENESS" },
      { ...makeCall("Chasing", "Engagement has shifted to pursuit."), category: "ENGAGEMENT EFFECTIVENESS" },
    ],
  },
  {
    category: "TARGET STATUS (SHARED TRUTH)",
    calls: [
      { ...makeCall("Red (TARGET)", "Target is in critical state and should be finished."), category: "TARGET STATUS (SHARED TRUTH)" },
    ],
  },
  {
    category: "KILL / DEATH",
    calls: [
      { ...makeCall("Splash", "Target destroyed.", "Shared truth call-out."), category: "KILL / DEATH" },
      { ...makeCall("Full kill", "Confirmed target elimination."), category: "KILL / DEATH" },
      { ...makeCall("Down (TARGET)", "Target disabled but not confirmed destroyed."), category: "KILL / DEATH" },
      { ...makeCall("Down (PERSONAL)", "You are downed/out of the fight."), category: "KILL / DEATH" },
      { ...makeCall("Dead", "You are dead; no further comms."), category: "KILL / DEATH" },
    ],
  },
];

let data = [];
let adminMode = false;
let allowNameEdit = false;
let expandedAll = false;

const elements = {
  categoryNav: document.getElementById("categoryNav"),
  categorySections: document.getElementById("categorySections"),
  search: document.getElementById("search"),
  expandAll: document.getElementById("expandAll"),
  collapseAll: document.getElementById("collapseAll"),
  saveData: document.getElementById("saveData"),
  resetData: document.getElementById("resetData"),
  exportData: document.getElementById("exportData"),
  importData: document.getElementById("importData"),
  adminToggle: document.getElementById("adminToggle"),
  adminStatus: document.getElementById("adminStatus"),
  adminDialog: document.getElementById("adminDialog"),
  adminPassword: document.getElementById("adminPassword"),
  adminSubmit: document.getElementById("adminSubmit"),
  nameEdit: document.getElementById("nameEdit"),
  nameEditWrap: document.getElementById("nameEditWrap"),
};

const slugify = (value) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "");

const cloneDefault = () => JSON.parse(JSON.stringify(DEFAULT_DATA));

const loadData = () => {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored) {
    try {
      return JSON.parse(stored);
    } catch (error) {
      console.warn("Failed to parse stored data", error);
    }
  }
  return cloneDefault();
};

const saveData = () => {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
};

const updateAdminUI = () => {
  elements.adminStatus.textContent = adminMode ? "Admin" : "Viewer";
  elements.adminToggle.textContent = adminMode ? "Lock" : "Admin";
  elements.nameEditWrap.style.display = adminMode ? "flex" : "none";
  if (!adminMode) {
    allowNameEdit = false;
    elements.nameEdit.checked = false;
    localStorage.removeItem(NAME_EDIT_KEY);
  }
};

const filterMatch = (call, query) => {
  if (!query) return true;
  const haystack = [
    call.callName,
    call.category,
    call.context,
    call.meaning,
    call.responseExpected,
    call.notes,
    ...(call.whenToUse || []),
  ]
    .join(" ")
    .toLowerCase();
  return haystack.includes(query);
};

const renderNav = () => {
  elements.categoryNav.innerHTML = "";
  data.forEach((category) => {
    const link = document.createElement("a");
    link.href = `#${slugify(category.category)}`;
    link.textContent = category.category;
    elements.categoryNav.appendChild(link);
  });
};

const createField = (labelText, inputElement) => {
  const wrapper = document.createElement("div");
  wrapper.className = "field";
  const label = document.createElement("label");
  label.textContent = labelText;
  wrapper.appendChild(label);
  wrapper.appendChild(inputElement);
  return wrapper;
};

const createTextInput = (value, onChange, disabled = false) => {
  const input = document.createElement("input");
  input.type = "text";
  input.value = value || "";
  input.disabled = disabled;
  if (!disabled) {
    input.addEventListener("input", (event) => onChange(event.target.value));
  }
  return input;
};

const createTextarea = (value, onChange, disabled = false) => {
  const textarea = document.createElement("textarea");
  textarea.value = value || "";
  textarea.readOnly = disabled;
  if (!disabled) {
    textarea.addEventListener("input", (event) => onChange(event.target.value));
  }
  return textarea;
};

const createSelect = (options, value, onChange, disabled = false) => {
  const select = document.createElement("select");
  select.disabled = disabled;
  options.forEach((optionValue) => {
    const option = document.createElement("option");
    option.value = optionValue;
    option.textContent = optionValue;
    if (optionValue === value) {
      option.selected = true;
    }
    select.appendChild(option);
  });
  if (!disabled) {
    select.addEventListener("change", (event) => onChange(event.target.value));
  }
  return select;
};

const renderCall = (call, categoryIndex, callIndex) => {
  const card = document.createElement("article");
  card.className = "call-card";

  const header = document.createElement("div");
  header.className = "call-header";

  const toggleButton = document.createElement("button");
  toggleButton.className = "ghost";
  toggleButton.textContent = "▸";
  toggleButton.addEventListener("click", () => {
    body.classList.toggle("collapsed");
    const isCollapsed = body.classList.contains("collapsed");
    toggleButton.textContent = isCollapsed ? "▸" : "▾";
  });

  const nameInput = createTextInput(
    call.callName,
    (value) => {
      call.callName = value;
    },
    !adminMode || !allowNameEdit
  );

  const adminControls = document.createElement("div");
  adminControls.className = "inline-controls";

  if (adminMode) {
    const moveUp = document.createElement("button");
    moveUp.className = "ghost";
    moveUp.textContent = "↑";
    moveUp.title = "Move up";
    moveUp.disabled = callIndex === 0;
    moveUp.addEventListener("click", () => {
      const calls = data[categoryIndex].calls;
      [calls[callIndex - 1], calls[callIndex]] = [calls[callIndex], calls[callIndex - 1]];
      render();
    });

    const moveDown = document.createElement("button");
    moveDown.className = "ghost";
    moveDown.textContent = "↓";
    moveDown.title = "Move down";
    moveDown.disabled = callIndex === data[categoryIndex].calls.length - 1;
    moveDown.addEventListener("click", () => {
      const calls = data[categoryIndex].calls;
      [calls[callIndex + 1], calls[callIndex]] = [calls[callIndex], calls[callIndex + 1]];
      render();
    });

    const removeCall = document.createElement("button");
    removeCall.className = "ghost";
    removeCall.textContent = "Delete";
    removeCall.addEventListener("click", () => {
      data[categoryIndex].calls.splice(callIndex, 1);
      render();
    });

    adminControls.append(moveUp, moveDown, removeCall);
  }

  header.append(toggleButton, nameInput, adminControls);

  const body = document.createElement("div");
  body.className = "call-body";
  if (!expandedAll) {
    body.classList.add("collapsed");
    toggleButton.textContent = "▸";
  } else {
    toggleButton.textContent = "▾";
  }

  const categorySelect = createSelect(
    data.map((item) => item.category),
    call.category,
    (value) => {
      if (value === call.category) return;
      const previousCategory = data[categoryIndex];
      previousCategory.calls.splice(callIndex, 1);
      const targetCategory = data.find((item) => item.category === value);
      if (targetCategory) {
        call.category = value;
        targetCategory.calls.push(call);
      } else {
        previousCategory.calls.splice(callIndex, 0, call);
      }
      render();
    },
    !adminMode
  );

  const contextArea = createTextarea(call.context, (value) => {
    call.context = value;
  }, !adminMode);

  const meaningArea = createTextarea(call.meaning, (value) => {
    call.meaning = value;
  }, !adminMode);

  const whenList = document.createElement("div");
  whenList.className = "list-items";
  (call.whenToUse || []).forEach((item, index) => {
    const itemRow = document.createElement("div");
    itemRow.className = "list-item";
    const itemInput = createTextInput(item, (value) => {
      call.whenToUse[index] = value;
    }, !adminMode);
    itemRow.appendChild(itemInput);
    if (adminMode) {
      const removeItem = document.createElement("button");
      removeItem.className = "ghost";
      removeItem.textContent = "Remove";
      removeItem.addEventListener("click", () => {
        call.whenToUse.splice(index, 1);
        render();
      });
      itemRow.appendChild(removeItem);
    }
    whenList.appendChild(itemRow);
  });

  const addItemButton = document.createElement("button");
  addItemButton.className = "ghost";
  addItemButton.textContent = "Add bullet";
  addItemButton.addEventListener("click", () => {
    call.whenToUse.push("New bullet");
    render();
  });

  const responseInput = createTextInput(call.responseExpected, (value) => {
    call.responseExpected = value;
  }, !adminMode);

  const notesArea = createTextarea(call.notes, (value) => {
    call.notes = value;
  }, !adminMode);

  body.append(
    createField("Category", categorySelect),
    createField("Context", contextArea),
    createField("Meaning", meaningArea),
    createField("When to use", whenList),
    adminMode ? addItemButton : document.createElement("span"),
    createField("Response expected", responseInput),
    createField("Notes", notesArea)
  );

  card.append(header, body);
  return card;
};

const render = () => {
  elements.categorySections.innerHTML = "";
  renderNav();
  const query = elements.search.value.trim().toLowerCase();

  data.forEach((category, categoryIndex) => {
    const section = document.createElement("section");
    section.className = "category-section";
    section.id = slugify(category.category);

    const header = document.createElement("div");
    header.className = "category-header";

    const title = document.createElement("h3");
    title.textContent = category.category;

    const headerControls = document.createElement("div");
    headerControls.className = "inline-controls";

    if (adminMode) {
      const addCall = document.createElement("button");
      addCall.textContent = "Add call";
      addCall.addEventListener("click", () => {
        category.calls.push({
          ...makeCall("New call"),
          category: category.category,
        });
        render();
      });
      headerControls.appendChild(addCall);
    }

    header.append(title, headerControls);

    const list = document.createElement("div");
    list.className = "call-list";

    category.calls.forEach((call, callIndex) => {
      const card = renderCall(call, categoryIndex, callIndex);
      if (!filterMatch(call, query)) {
        card.classList.add("hidden");
      }
      list.appendChild(card);
    });

    section.append(header, list);
    elements.categorySections.appendChild(section);
  });

  updateAdminUI();
};

const setAdminMode = (value) => {
  adminMode = value;
  localStorage.setItem(ADMIN_KEY, adminMode ? "1" : "0");
  updateAdminUI();
  render();
};

const handleAdminToggle = async () => {
  if (adminMode) {
    setAdminMode(false);
    return;
  }
  elements.adminPassword.value = "";
  elements.adminDialog.showModal();
};

const handleAdminSubmit = async () => {
  const password = elements.adminPassword.value;
  const hash = await hashPassword(password);
  if (hash === ADMIN_PASSWORD_HASH) {
    setAdminMode(true);
    elements.adminDialog.close();
  } else {
    alert("Incorrect password.");
  }
};

const hashPassword = async (password) => {
  const buffer = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(password)
  );
  return Array.from(new Uint8Array(buffer))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
};

const exportJson = () => {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "space-comms-protocol.json";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
};

const importJson = (file) => {
  const reader = new FileReader();
  reader.onload = () => {
    try {
      const parsed = JSON.parse(reader.result);
      if (!Array.isArray(parsed)) {
        throw new Error("Invalid JSON format");
      }
      data = parsed;
      saveData();
      render();
    } catch (error) {
      alert("Invalid JSON file.");
    }
  };
  reader.readAsText(file);
};

const setupListeners = () => {
  elements.search.addEventListener("input", render);
  elements.expandAll.addEventListener("click", () => {
    expandedAll = true;
    render();
  });
  elements.collapseAll.addEventListener("click", () => {
    expandedAll = false;
    render();
  });
  elements.saveData.addEventListener("click", () => {
    saveData();
    alert("Saved to localStorage.");
  });
  elements.resetData.addEventListener("click", () => {
    if (confirm("Reset all data to default?")) {
      data = cloneDefault();
      localStorage.removeItem(STORAGE_KEY);
      render();
    }
  });
  elements.exportData.addEventListener("click", exportJson);
  elements.importData.addEventListener("change", (event) => {
    if (event.target.files.length) {
      importJson(event.target.files[0]);
      event.target.value = "";
    }
  });
  elements.adminToggle.addEventListener("click", handleAdminToggle);
  elements.adminSubmit.addEventListener("click", (event) => {
    event.preventDefault();
    handleAdminSubmit();
  });
  elements.nameEdit.addEventListener("change", (event) => {
    allowNameEdit = event.target.checked;
    localStorage.setItem(NAME_EDIT_KEY, allowNameEdit ? "1" : "0");
    render();
  });
};

const init = () => {
  data = loadData();
  adminMode = localStorage.getItem(ADMIN_KEY) === "1";
  allowNameEdit = localStorage.getItem(NAME_EDIT_KEY) === "1";
  elements.nameEdit.checked = allowNameEdit;
  setupListeners();
  render();
};

init();
