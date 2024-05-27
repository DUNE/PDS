#define wfdaphne_cxx
#include "functions/wfdaphne.h"
#include <TH2.h>
#include <TStyle.h>
#include <TCanvas.h>
#include "functions/wffunctions.h"

template <typename S>
ostream &operator<<(ostream &os,
                    const vector<S> &vector)
{
    for (auto element : vector)
    {
        os << element << " ";
    }
    return os;
}

void wfdaphne::Loop() {};

// Usage: root 'waveforms.C("file.root",run_number)' -b -q

void waveforms(TString inputfile, int run)
{

    ROOT::EnableThreadSafety();
    ROOT::EnableImplicitMT(4);

    wffunctions bs;

    map<TString, TString> filename = {
        {"file1", Form("%s", inputfile.Data())}};

    TFile hf(Form("run_%i.root", run), "recreate"); // create root file with charge and persistence histograms per channel
    // hf.Close();
    hf.mkdir("chargehistos");
    hf.mkdir("persistancehistos");

    for (auto f : filename)
    {

        TChain *t[] = {NULL};

        t[0] = new TChain();
        t[0]->Add(Form("%s?#pdhddaphne/waveforms", f.second.Data()));
        t[0]->SetImplicitMT(true);
        Long64_t nentries = t[0]->GetEntries();
        wfdaphne event(t[0]);

        cout << "\nFile open -> " << f.second << "\tentries: " << nentries << endl;

        int hl = -50; // Low Y-axis for persistance plot
        int hh = 310; // High Y-axis for persistance plot

        int binlimlow = 100;  // Low X-axis for persistance plot
        int binlimhigh = 300; // High X-axis for persistance plot

        string s = f.second.Data();
        int pos = s.find("/run");
        int pos2 = s.find("_dataflow0");
        // TString sub = s.substr(pos + 1, s.length() - pos2);
        TString sub = s.substr(pos + 1, pos2 - pos - 1);
        TString inp = sub.ReplaceAll(".root", "");
        cout << sub << " " << pos << " " << pos2 << endl;

        TH2F *wfpersistenceall[160];
        TH1D *chg[160];

        for (int i = 0; i < 160; i++) // create histograms
        {
            wfpersistenceall[i] = new TH2F(Form("persistence_channel_%i", i), Form("persistence_channel_%i", i), (binlimhigh - binlimlow), binlimlow, binlimhigh, (hh - hl), hl, hh);
            chg[i] = new TH1D(Form("charge_channel_%i", i), Form("charge_channel_%i_run", i), 200, -150, 2500);
        }

        std::vector<std::pair<ULong64_t, ULong64_t>> data;
        std::map<std::pair<ULong64_t, ULong64_t>, ULong64_t> frequency;

        for (auto ievt : ROOT::TSeqUL(nentries)) // loop over entries in root file
        {
            event.GetEntry(ievt);

            std::vector<int> adcv; // vector of adc values
            for (int i = 0; i < 1024; i++)
            {
                int adc = event.adc_channel[i];
                adcv.push_back(adc); // filling adc vector
            }

            bs.setADCvector(adcv); // setting the adc vector to use function

            bs.setWindowBaseline(100);         // set window to calculate baseline from 0 to number, this case o to 100 ticks
            int basel = bs.getLimitBaseline(); // mean value baseline of the first 100 ticks

            bs.setWindowCharge(134, 170);                                         // set window to calculate the charge
            int integ = bs.fillChargeHistogram(chg[event.OfflineChannel], basel); // filling charge histo

            bs.fillWaveform2D(wfpersistenceall[event.OfflineChannel], basel); // filling persistence histo
        }

        std::ifstream file_map("functions/APAchannelmap.txt"); // reading channel map
        size_t sl, lk, dpch, ch;
        std::stringstream ssmap;
        std::map<size_t, std::tuple<size_t, size_t, size_t>> detmap;
        std::string line;

        if (file_map.is_open())
        {
            while (getline(file_map, line))
            {
                ssmap.clear();
                ssmap.str(line);

                while (ssmap >> sl >> lk >> dpch >> ch)
                {
                    detmap[ch] = std::make_tuple(sl, lk, dpch);
                }
            }

            file_map.close();
        }
        else
        {
            std::cerr << "Unable to open file!" << std::endl;
            file_map.close();
        }

        TCanvas *c = new TCanvas("", "", 8000, 8000);
        c->Divide(2, 1);
        TVirtualPad *c1_1 = c->cd(1);
        TVirtualPad *c1_2 = c->cd(2);
        c1_1->Divide(4, 10, 0.00000, 0.00000);
        c1_2->Divide(4, 10, 0.00000, 0.00000);

        TCanvas *c2 = new TCanvas("", "", 8000, 8000);
        c2->Divide(2, 1);
        TVirtualPad *c2_1 = c2->cd(1);
        TVirtualPad *c2_2 = c2->cd(2);
        c2_1->Divide(4, 10, 0.00000, 0.00000);
        c2_2->Divide(4, 10, 0.00000, 0.00000);

        TCanvas *c3 = new TCanvas("", "", 8000, 8000);
        c3->Divide(2, 1);
        TVirtualPad *c3_1 = c3->cd(1);
        TVirtualPad *c3_2 = c3->cd(2);
        c3_1->Divide(4, 10, 0.00000, 0.00000);
        c3_2->Divide(4, 10, 0.00000, 0.00000);

        TCanvas *c4 = new TCanvas("", "", 8000, 8000);
        c4->Divide(2, 1);
        TVirtualPad *c4_1 = c4->cd(1);
        TVirtualPad *c4_2 = c4->cd(2);
        c4_1->Divide(4, 10, 0.00000, 0.00000);
        c4_2->Divide(4, 10, 0.00000, 0.00000);

        gStyle->SetOptStat(0);
        gStyle->SetTitleSize(0.2, "t");
        // gStyle->SetTitleFontSize(0.6);
        gStyle->SetTitleX(0.5);
        gStyle->SetTitleY(1);

        for (int j = 1; j <= 4; j++) // plotting according map
        {
            for (int i = 1; i <= 10; i++) // plotting according map
            {
                c1_2->cd(4 * (i - 1) + j);
                chg[i + 79 + 10 * (4 - j)]->SetTitle(Form("EP %lu - Link %lu - Ch %lu", get<0>(detmap[i + 79 + 10 * (4 - j)]), get<1>(detmap[i + 79 + 10 * (4 - j)]), get<2>(detmap[i + 79 + 10 * (4 - j)])));
                chg[i + 79 + 10 * (4 - j)]->Draw("histo");
                gPad->SetTopMargin(0.2);
                c1_2->Modified();
                c1_2->Update();

                c1_1->cd(4 * (i - 1) + j);
                chg[i + 119 + 10 * (4 - j)]->SetTitle(Form("EP %lu - Link %lu - Ch %lu", get<0>(detmap[i + 119 + 10 * (4 - j)]), get<1>(detmap[i + 119 + 10 * (4 - j)]), get<2>(detmap[i + 119 + 10 * (4 - j)])));
                chg[i + 119 + 10 * (4 - j)]->Draw("histo");
                gPad->SetTopMargin(0.2);
                c1_1->Modified();
                c1_1->Update();

                ///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

                c2_2->cd(4 * (i - 1) + j);
                wfpersistenceall[i + 79 + 10 * (4 - j)]->SetTitle(Form("EP %lu - Link %lu - Ch %lu", get<0>(detmap[i + 79 + 10 * (4 - j)]), get<1>(detmap[i + 79 + 10 * (4 - j)]), get<2>(detmap[i + 79 + 10 * (4 - j)])));
                wfpersistenceall[i + 79 + 10 * (4 - j)]->Draw("histo");
                gPad->SetTopMargin(0.2);
                c2_2->Modified();
                c2_2->Update();

                c2_1->cd(4 * (i - 1) + j);
                wfpersistenceall[i + 119 + 10 * (4 - j)]->SetTitle(Form("EP %lu - Link %lu - Ch %lu", get<0>(detmap[i + 119 + 10 * (4 - j)]), get<1>(detmap[i + 119 + 10 * (4 - j)]), get<2>(detmap[i + 119 + 10 * (4 - j)])));
                wfpersistenceall[i + 119 + 10 * (4 - j)]->Draw("histo");
                gPad->SetTopMargin(0.2);
                c2_1->Modified();
                c2_1->Update();

                ///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
                ///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
                ///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

                c3_2->cd(4 * (i - 1) + j);
                chg[i - 1 + 10 * (4 - j)]->SetTitle(Form("EP %lu - Link %lu - Ch %lu - Entries: %0.f", get<0>(detmap[i - 1 + 10 * (4 - j)]), get<1>(detmap[i - 1 + 10 * (4 - j)]), get<2>(detmap[i - 1 + 10 * (4 - j)]), chg[i - 1 + 10 * (4 - j)]->GetEntries()));
                chg[i - 1 + 10 * (4 - j)]->Draw("histo");
                gPad->SetTopMargin(0.2);
                c3_2->Modified();
                c3_2->Update();

                c3_1->cd(4 * (i - 1) + j);
                chg[i + 39 + 10 * (4 - j)]->SetTitle(Form("EP %lu - Link %lu - Ch %lu - Entries: %0.f", get<0>(detmap[i + 39 + 10 * (4 - j)]), get<1>(detmap[i + 39 + 10 * (4 - j)]), get<2>(detmap[i + 39 + 10 * (4 - j)]), chg[i + 39 + 10 * (4 - j)]->GetEntries()));
                chg[i + 39 + 10 * (4 - j)]->Draw("histo");
                gPad->SetTopMargin(0.2);
                c3_1->Modified();
                c3_1->Update();

                ///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

                c4_2->cd(4 * (i - 1) + j);
                wfpersistenceall[i - 1 + 10 * (4 - j)]->SetTitle(Form("EP %lu - Link %lu - Ch %lu", get<0>(detmap[i - 1 + 10 * (4 - j)]), get<1>(detmap[i - 1 + 10 * (4 - j)]), get<2>(detmap[i - 1 + 10 * (4 - j)])));
                wfpersistenceall[i - 1 + 10 * (4 - j)]->Draw("histo");
                gPad->SetTopMargin(0.2);
                c4_2->Modified();
                c4_2->Update();

                c4_1->cd(4 * (i - 1) + j);
                wfpersistenceall[i + 39 + 10 * (4 - j)]->SetTitle(Form("EP %lu - Link %lu - Ch %lu", get<0>(detmap[i + 39 + 10 * (4 - j)]), get<1>(detmap[i + 39 + 10 * (4 - j)]), get<2>(detmap[i + 39 + 10 * (4 - j)])));
                wfpersistenceall[i + 39 + 10 * (4 - j)]->Draw("histo");
                gPad->SetTopMargin(0.2);
                c4_1->Modified();
                c4_1->Update();
            }
        }

        c->Modified();
        c2->Modified();
        c3->Modified();
        c4->Modified();
        c->Update();
        c2->Update();
        c3->Update();
        c4->Update();
        c->SaveAs(Form("run_%i_charge_side_1.png", run));
        c2->SaveAs(Form("run_%i_persistence_side_1.png", run));
        c3->SaveAs(Form("run_%i_charge_side2.png", run));
        c4->SaveAs(Form("run_%i_persistence_side2.png", run));

        for (int i = 0; i < 160; i++)
        {
            int entriesh = wfpersistenceall[i]->GetEntries();
            if (entriesh != 0)
            {
                hf.cd("persistancehistos");
                wfpersistenceall[i]->Write();
            }
            int entriesc = chg[i]->GetEntries();
            if (entriesc != 0)
            {
                hf.cd("chargehistos");
                chg[i]->Write();
            }
        }
    }
}