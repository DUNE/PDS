//////////////////////////////////////////////////////////
// This class has been automatically generated on
// Sat Apr 27 19:25:33 2024 by ROOT version 6.30/04
// from TTree WaveformTree/Waveforms Tree
// found on file: pdhd_daphne_decodermodule.root
//////////////////////////////////////////////////////////

#ifndef wfdaphne_h
#define wfdaphne_h

#include <TROOT.h>
#include <TChain.h>
#include <TFile.h>

// Header file for the classes stored in the TTree if any.

class wfdaphne {
public :
   TTree          *fChain;   //!pointer to the analyzed TTree or TChain
   Int_t           fCurrent; //!current Tree number in a TChain

// Fixed size dimensions of array or collections stored in the TTree if any.

   // Declaration of leaf types
   Int_t           Run;
   Int_t           Event;
   Int_t           TriggerNumber;
   ULong64_t       TimeStamp;
   ULong64_t       Window_begin;
   ULong64_t       Window_end;
   Int_t           Slot;
   Int_t           Crate;
   Int_t           DaphneChannel;
   Int_t           OfflineChannel;
   ULong64_t       FrameTimestamp;
   Short_t         adc_channel[1024];
   Int_t           TriggerSampleValue;
   Int_t           Threshold;
   Int_t           Baseline;

   // List of branches
   TBranch        *b_Run;   //!
   TBranch        *b_Event;   //!
   TBranch        *b_TriggerNumber;   //!
   TBranch        *b_TimeStamp;   //!
   TBranch        *b_Window_begin;   //!
   TBranch        *b_Window_end;   //!
   TBranch        *b_Slot;   //!
   TBranch        *b_Crate;   //!
   TBranch        *b_DaphneChannel;   //!
   TBranch        *b_OfflineChannel;   //!
   TBranch        *b_FrameTimestamp;   //!
   TBranch        *b_adc_value;   //!
   TBranch        *b_TriggerSampleValue;   //!
   TBranch        *b_Threshold;   //!
   TBranch        *b_Baseline;   //!

   wfdaphne(TTree *tree=0);
   virtual ~wfdaphne();
   virtual Int_t    Cut(Long64_t entry);
   virtual Int_t    GetEntry(Long64_t entry);
   virtual Long64_t LoadTree(Long64_t entry);
   virtual void     Init(TTree *tree);
   virtual void     Loop();
   virtual Bool_t   Notify();
   virtual void     Show(Long64_t entry = -1);
};

#endif

#ifdef wfdaphne_cxx
wfdaphne::wfdaphne(TTree *tree) : fChain(0) 
{
// if parameter tree is not specified (or zero), connect the file
// used to generate this class and read the Tree.
   if (tree == 0) {
      TFile *f = (TFile*)gROOT->GetListOfFiles()->FindObject("pdhd_daphne_decodermodule.root");
      if (!f || !f->IsOpen()) {
         f = new TFile("pdhd_daphne_decodermodule.root");
      }
      TDirectory * dir = (TDirectory*)f->Get("pdhd_daphne_decodermodule.root:/pdhddaphne");
      dir->GetObject("WaveformTree",tree);

   }
   Init(tree);
}

wfdaphne::~wfdaphne()
{
   if (!fChain) return;
   delete fChain->GetCurrentFile();
}

Int_t wfdaphne::GetEntry(Long64_t entry)
{
// Read contents of entry.
   if (!fChain) return 0;
   return fChain->GetEntry(entry);
}
Long64_t wfdaphne::LoadTree(Long64_t entry)
{
// Set the environment to read one entry
   if (!fChain) return -5;
   Long64_t centry = fChain->LoadTree(entry);
   if (centry < 0) return centry;
   if (fChain->GetTreeNumber() != fCurrent) {
      fCurrent = fChain->GetTreeNumber();
      Notify();
   }
   return centry;
}

void wfdaphne::Init(TTree *tree)
{
   // The Init() function is called when the selector needs to initialize
   // a new tree or chain. Typically here the branch addresses and branch
   // pointers of the tree will be set.
   // It is normally not necessary to make changes to the generated
   // code, but the routine can be extended by the user if needed.
   // Init() will be called many times when running on PROOF
   // (once per file to be processed).

   // Set branch addresses and branch pointers
   if (!tree) return;
   fChain = tree;
   fCurrent = -1;
   fChain->SetMakeClass(1);

   fChain->SetBranchAddress("Run", &Run, &b_Run);
   fChain->SetBranchAddress("Event", &Event, &b_Event);
   fChain->SetBranchAddress("TriggerNumber", &TriggerNumber, &b_TriggerNumber);
   fChain->SetBranchAddress("TimeStamp", &TimeStamp, &b_TimeStamp);
   fChain->SetBranchAddress("Window_begin", &Window_begin, &b_Window_begin);
   fChain->SetBranchAddress("Window_end", &Window_end, &b_Window_end);
   fChain->SetBranchAddress("Slot", &Slot, &b_Slot);
   fChain->SetBranchAddress("Crate", &Crate, &b_Crate);
   fChain->SetBranchAddress("DaphneChannel", &DaphneChannel, &b_DaphneChannel);
   fChain->SetBranchAddress("OfflineChannel", &OfflineChannel, &b_OfflineChannel);
   fChain->SetBranchAddress("FrameTimestamp", &FrameTimestamp, &b_FrameTimestamp);
   fChain->SetBranchAddress("adc_channel", adc_channel, &b_adc_value);
   fChain->SetBranchAddress("TriggerSampleValue", &TriggerSampleValue, &b_TriggerSampleValue);
   fChain->SetBranchAddress("Threshold", &Threshold, &b_Threshold);
   fChain->SetBranchAddress("Baseline", &Baseline, &b_Baseline);
   Notify();
}

Bool_t wfdaphne::Notify()
{
   // The Notify() function is called when a new file is opened. This
   // can be either for a new TTree in a TChain or when when a new TTree
   // is started when using PROOF. It is normally not necessary to make changes
   // to the generated code, but the routine can be extended by the
   // user if needed. The return value is currently not used.

   return kTRUE;
}

void wfdaphne::Show(Long64_t entry)
{
// Print contents of entry.
// If entry is not specified, print current entry
   if (!fChain) return;
   fChain->Show(entry);
}
Int_t wfdaphne::Cut(Long64_t entry)
{
// This function may be called from Loop.
// returns  1 if entry is accepted.
// returns -1 otherwise.
   return 1;
}
#endif // #ifdef wfdaphne_cxx
