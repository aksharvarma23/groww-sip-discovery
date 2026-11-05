/**
 * Creates the SIP experience survey as a Google Form, with branching,
 * plus a linked Google Sheet for the responses.
 * v3: no final open question or call opt-in; each status section ends the form.
 *
 * How to run:
 *   1. Go to https://script.google.com and click "New project".
 *   2. Delete the sample code, paste this whole file, and save (Ctrl+S).
 *   3. In the toolbar, pick the function "createSipSurvey" and click Run.
 *   4. Allow the permissions. Google will say the app is unverified because it
 *      is your own script: click Advanced > Go to project (unsafe) > Allow.
 *   5. Open the Execution log at the bottom. It shows the link to share, the
 *      edit link and the responses sheet.
 *
 * Every run creates a new, separate form. Delete old test forms from Drive.
 */
function createSipSurvey() {
  var form = FormApp.create('Your SIP experience (5-minute survey)');
  form.setDescription(
    'A student research project on what happens after people start a SIP. ' +
    'It takes about 5 minutes.\n\n' +
    'It is anonymous unless you choose to leave contact details at the end. ' +
    'We never ask for account numbers, PAN or screenshots.\n\n' +
    'You must be 18 or older to take part.');
  form.setProgressBar(true);
  form.setCollectEmail(false);
  form.setAllowResponseEdits(false);
  form.setShowLinkToRespondAgain(false);
  form.setConfirmationMessage('Thank you! Your answers help us understand what makes SIPs easier to stick with.');

  // ---------- Page 1: consent ----------
  var qConsent = form.addMultipleChoiceItem()
    .setTitle('Are you 18 or older, and happy to take part?')
    .setRequired(true);

  // ---------- Page 2: screener ----------
  form.addPageBreakItem().setTitle('About SIPs');
  var qEver = form.addMultipleChoiceItem()
    .setTitle('Have you ever started a SIP?')
    .setHelpText('A SIP (Systematic Investment Plan) puts a fixed amount into a mutual fund ' +
                 'automatically, usually every month.')
    .setRequired(true);

  // ---------- Page 3: first SIP ----------
  form.addPageBreakItem().setTitle('Your first SIP')
    .setHelpText('If you have more than one SIP, answer about the first one you started.');
  mc(form, 'Before your first SIP, had you invested in mutual funds in any other way?',
     ['No, the SIP was my first', 'Yes, I had invested before (for example, a one-time investment)']);
  mc(form, 'When did you start your first SIP?',
     ['Less than 6 months ago', '6-12 months ago', '1-2 years ago', '2-3 years ago', 'More than 3 years ago']);
  mc(form, 'Which app did you start it on?',
     ['Groww', 'Zerodha (Coin or Kite)', 'Paytm Money', 'INDmoney', 'ET Money',
      'A bank app or the fund house website', 'Through an agent or advisor', "Don't remember"], true);

  // ---------- Page 4: about you ----------
  form.addPageBreakItem().setTitle('About you');
  mc(form, 'How old are you?', ['18-21', '22-25', '26-30', '31-35', '36 or older']);
  mc(form, 'What were you doing when you started the SIP?',
     ['Studying', 'Studying, with a stipend or part-time income', 'In my first job (0-2 years)',
      'Working for more than 2 years', 'Running my own business or freelancing', 'Not working'], true);
  mc(form, 'Where did the money for the SIP come from, at the start?',
     ['My salary', 'My parents or family (including pocket money)', 'Stipend, internship or freelance pay',
      'My savings', 'A mix of these']);
  mc(form, 'Did that money come in regularly every month?',
     ['Yes, about the same amount every month', 'Yes, but the amount changed month to month',
      'No, it was irregular']);

  // ---------- Page 5: starting ----------
  form.addPageBreakItem().setTitle('Starting the SIP');
  mc(form, 'Who mainly got you to start?',
     ['It was my own idea', 'My family told me to', 'My family set it up for me', 'Friends or colleagues',
      'YouTube or Instagram', 'My employer', 'The app suggested it']);
  mc(form, 'When you started, could you have explained to a friend what your fund invests in?',
     ['Yes, clearly', 'Roughly', "I only knew the fund's name", 'No']);
  mc(form, 'When you started, how soon did you expect to see a good return?',
     ['Within a few months', 'Within a year', 'In 1-3 years', 'In 5 years or more', "I didn't think about it"]);

  // ---------- Page 6: checking ----------
  form.addPageBreakItem().setTitle('Checking on it');
  mc(form, 'How often do (or did) you open the app to check your SIP?',
     ['Every day', 'A few times a week', 'About once a month', 'Only when money gets debited', 'Rarely or never']);
  mc(form, 'When you check, what do you look at first?',
     ['Total current value', 'Profit or loss in rupees', 'Return in %', 'XIRR (yearly return)',
      "Today's up or down change", "I don't really look at the numbers"]);
  var qDoubt = form.addMultipleChoiceItem()
    .setTitle('Have you ever thought about stopping or pausing your SIP?')
    .setRequired(true);

  // ---------- Page 7: doubt (only if they thought about stopping) ----------
  form.addPageBreakItem().setTitle('When you thought about stopping');
  form.addCheckboxItem()
    .setTitle('What made you think about it? (pick all that apply)')
    .setChoiceValues(['The profit looked too small', 'It was showing a loss', 'News about the market falling',
                      'Something someone said to me', "The 'money will be debited' message",
                      'I needed the money for something else', 'Other funds seemed to be doing better',
                      'The app was confusing'])
    .showOtherOption(true)
    .setRequired(true);
  var qDidWhat = form.addCheckboxItem()
    .setTitle('What did you do next? (pick all that apply)')
    .setChoiceValues(['Asked family', 'Asked friends', 'Watched YouTube videos', 'Read Reddit or forums',
                      'Searched on Google', "Used the app's help section", "Nothing, I didn't look into it"])
    .setRequired(true);
  mc(form, 'Did that clear your doubt?',
     ['Yes', 'Partly', 'No', "I didn't look for an answer"]);

  // ---------- Page 8: status ----------
  var brStatus = form.addPageBreakItem().setTitle('Your first SIP today');
  var qStatus = form.addMultipleChoiceItem()
    .setTitle("What's happening with your first SIP now?")
    .setRequired(true);

  // ---------- Page 9: I stopped it ----------
  var brStopped = form.addPageBreakItem().setTitle('Stopping the SIP');
  form.addCheckboxItem()
    .setTitle('How did you stop it? (pick all that apply)')
    .setChoiceValues(['Cancelled the SIP in the investing app',
                      'Turned off AutoPay or the mandate in GPay, PhonePe or my bank app',
                      'Stopped keeping money in that bank account',
                      'Withdrew the money', "Don't remember"])
    .showOtherOption(true)
    .setRequired(true);
  mc(form, 'When you stopped, did you plan to start again later?',
     ['Yes, and I already have', "Yes, but I haven't got to it yet", 'No']);

  // ---------- Page 10: it stopped by itself ----------
  var brFailed = form.addPageBreakItem().setTitle('When the payments failed');
  form.addCheckboxItem()
    .setTitle('Why did the payments fail, as far as you know? (pick all that apply)')
    .setChoiceValues(["The money wasn't in the account on the debit date",
                      'AutoPay or the mandate was turned off or expired',
                      'I changed or closed that bank account', "I don't know"])
    .showOtherOption(true)
    .setRequired(true);
  mc(form, 'Did you try to fix it?',
     ["Yes, and it's running again", "I meant to, but haven't yet", "No, I let it go"]);

  // ---------- Page 11: I skipped some months ----------
  var brSkipped = form.addPageBreakItem().setTitle('Skipping months');
  form.addCheckboxItem()
    .setTitle('How did those months get skipped? (pick all that apply)')
    .setChoiceValues(["Used the 'skip instalment' option in the app",
                      'Paused AutoPay in GPay, PhonePe or my bank app',
                      "Didn't keep enough money in the account", "A payment failed and I didn't fix it",
                      "Don't remember"])
    .showOtherOption(true)
    .setRequired(true);

  // ---------- Page 12: not sure ----------
  var brUnsure = form.addPageBreakItem().setTitle('Not sure if it is running');
  form.addCheckboxItem()
    .setTitle("Why aren't you sure? (pick all that apply)")
    .setChoiceValues(["I haven't checked in a long time", 'Someone else manages it for me',
                      'I changed my bank account or phone number', 'I saw a payment-failed message',
                      'I turned off AutoPay somewhere and am not sure what happened'])
    .showOtherOption(true)
    .setRequired(true);

  // ---------- Branching ----------
  var SUBMIT = FormApp.PageNavigationType.SUBMIT;
  var NEXT = FormApp.PageNavigationType.CONTINUE;

  qConsent.setChoices([qConsent.createChoice("Yes, I'm 18 or older and happy to take part", NEXT),
                       qConsent.createChoice('No', SUBMIT)]);
  qEver.setChoices([qEver.createChoice('Yes', NEXT),
                    qEver.createChoice('No', SUBMIT)]);
  qDoubt.setChoices([qDoubt.createChoice('Yes, many times', NEXT),
                     qDoubt.createChoice('Once or twice', NEXT),
                     qDoubt.createChoice('Never', brStatus)]);
  qStatus.setChoices([qStatus.createChoice('Still running: money goes in every month', SUBMIT),
                      qStatus.createChoice("Still running, but I've skipped some months", brSkipped),
                      qStatus.createChoice('I stopped it', brStopped),
                      qStatus.createChoice('It stopped by itself (payments failed)', brFailed),
                      qStatus.createChoice("I'm not sure", brUnsure)]);

  // Each status section ends the form. A page break's go-to applies when it is
  // reached by moving forward from the section before it.
  brFailed.setGoToPage(SUBMIT);   // after "Stopping the SIP"
  brSkipped.setGoToPage(SUBMIT);  // after "When the payments failed"
  brUnsure.setGoToPage(SUBMIT);   // after "Skipping months"
  // "Not sure if it is running" is the last section, so it submits on its own.

  // ---------- Responses sheet ----------
  var ss = SpreadsheetApp.create('SIP survey responses');
  form.setDestination(FormApp.DestinationType.SPREADSHEET, ss.getId());

  Logger.log('Share this link:  ' + form.getPublishedUrl());
  Logger.log('Edit the form:    ' + form.getEditUrl());
  Logger.log('Responses sheet:  ' + ss.getUrl());
}

/** Required single-choice question; optionally with an "Other" text box. */
function mc(form, title, choices, withOther) {
  var item = form.addMultipleChoiceItem().setTitle(title).setChoiceValues(choices).setRequired(true);
  if (withOther) item.showOtherOption(true);
  return item;
}
