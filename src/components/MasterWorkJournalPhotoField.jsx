import React from 'react';

import PhotoAttachmentField from './PhotoAttachmentField';


export default function MasterWorkJournalPhotoField(props) {
  return (
    <PhotoAttachmentField
      {...props}
      context="work-journal"
      protectedPreview
    />
  );
}
