const userId = value => {
  const id = Number(value);
  return Number.isSafeInteger(id) && id > 0 ? id : null;
};

// An identified document never belongs to another account merely because its
// recorded name matches. Name matching is retained for historical documents.
export const materialPersonMatches = (recordId, recordName, personId, personName) => {
  if (recordId !== null && recordId !== undefined && recordId !== '') {
    return userId(recordId) !== null && userId(recordId) === userId(personId);
  }
  return !!personName && recordName === personName;
};

export const materialReturnMatchesPerson = (row, personId, personName) => {
  if ((row.sourceType || row.source_type) === 'material_return_user') {
    const id = userId(row.sourceId ?? row.source_id);
    return id !== null && id === userId(personId);
  }
  return materialPersonMatches(null, row.issuedBy || row.issued_by, personId, personName);
};

// The personnel row primary key belongs to staff, not users.
export const materialRecipientUserId = person => userId(person?.accessUserId ?? person?.access_user_id) || '';
